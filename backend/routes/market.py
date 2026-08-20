"""Staff-only Property Data Aggregation and Master Property link endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query

from core.account_policy import account_category
from core.collectors import get_collector
from core.db import db, new_id, now_iso
from core.market_property_link import MarketPropertyLinkService, collector_payload
from core.security import get_current_user
from models import MarketObservationCreate, MarketSourceCreate

router = APIRouter()
service = MarketPropertyLinkService(db)


async def require_staff(user: dict = Depends(get_current_user)) -> dict:
    if account_category(user) != "STAFF" or user.get("status", "ACTIVE") != "ACTIVE":
        raise HTTPException(403, "Staff account required")
    return user


@router.get("/admin/market/sources")
async def list_sources(user: dict = Depends(require_staff)):
    return await db.source_sites.find({}, {"_id": 0}).sort("name", 1).to_list(500)


@router.post("/admin/market/sources")
async def create_source(payload: MarketSourceCreate, user: dict = Depends(require_staff)):
    if await db.source_sites.find_one({"domain": payload.domain.lower()}, {"_id": 0, "id": 1}):
        raise HTTPException(409, "Source domain already exists")
    document = {
        "id": new_id(), **payload.model_dump(), "domain": payload.domain.lower(),
        "created_at": now_iso(), "updated_at": now_iso(),
    }
    await db.source_sites.insert_one(document)
    document.pop("_id", None)
    return document


@router.post("/admin/market/listings")
async def ingest_market_listing(payload: MarketObservationCreate, user: dict = Depends(require_staff)):
    try:
        return await service.ingest(payload.model_dump(), user["id"])
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.post("/admin/market/sources/{source_site_id}/collect")
async def collect_source(source_site_id: str, user: dict = Depends(require_staff)):
    source = await db.source_sites.find_one({"id": source_site_id}, {"_id": 0})
    if not source or not source.get("active", True):
        raise HTTPException(404, "Active source site not found")
    collector_class = get_collector(source.get("collector_key") or "")
    if not collector_class:
        raise HTTPException(400, "Source site has no supported collector")
    run = {
        "id": new_id(), "source_site_id": source_site_id, "status": "RUNNING",
        "started_at": now_iso(), "finished_at": None, "records_seen": 0,
        "records_ingested": 0, "records_matched": 0, "records_review_required": 0,
        "created_by": user["id"],
    }
    await db.collection_runs.insert_one(run)
    try:
        collector = collector_class(source)
        async for row in collector.iter_listings():
            run["records_seen"] += 1
            normalized = collector_payload(source_site_id, row)
            if not normalized["source_listing_id"] or not normalized["source_url"] or normalized["price_amount"] is None:
                continue
            result = await service.ingest(normalized, user["id"])
            run["records_ingested"] += 1
            if result["match"]["status"] == "MATCHED":
                run["records_matched"] += 1
            elif result["match"]["status"] == "REVIEW_REQUIRED":
                run["records_review_required"] += 1
        run.update(status="SUCCESS", finished_at=now_iso())
    except Exception as exc:
        run.update(status="FAILED", finished_at=now_iso(), error=str(exc)[:1000])
        await db.collection_runs.update_one({"id": run["id"]}, {"$set": run})
        raise HTTPException(502, "Collector run failed")
    await db.collection_runs.update_one({"id": run["id"]}, {"$set": run})
    run.pop("_id", None)
    return run


@router.get("/admin/market/listings")
async def list_market_listings(
    limit: int = Query(default=100, ge=1, le=500),
    user: dict = Depends(require_staff),
):
    return await service.list_evidence(limit)


@router.get("/admin/market/summary")
async def market_summary(user: dict = Depends(require_staff)):
    return await service.summary()


@router.get("/admin/market/match-reviews")
async def list_match_reviews(user: dict = Depends(require_staff)):
    return await db.property_match_reviews.find({"status": "OPEN"}, {"_id": 0}).sort("created_at", 1).to_list(500)


@router.post("/admin/market/match-reviews/{review_id}/resolve")
async def resolve_match_review(review_id: str, payload: dict, user: dict = Depends(require_staff)):
    review = await db.property_match_reviews.find_one({"id": review_id, "status": "OPEN"}, {"_id": 0})
    if not review:
        raise HTTPException(404, "Open match review not found")
    decision = str(payload.get("decision") or "").upper()
    master_property_id = payload.get("master_property_id")
    if decision == "MATCHED":
        if master_property_id not in review.get("candidate_property_ids", []):
            raise HTTPException(400, "Select one of the reviewed Master Property candidates")
        if not await db.master_properties.find_one({"id": master_property_id}, {"_id": 0, "id": 1}):
            raise HTTPException(404, "Master Property not found")
        listing_patch = {"master_property_id": master_property_id, "match_status": "MATCHED", "match_confidence": 100, "match_rule": "STAFF_REVIEW", "updated_at": now_iso()}
    elif decision == "REJECTED":
        listing_patch = {"master_property_id": None, "match_status": "UNMATCHED", "match_confidence": 0, "match_rule": "STAFF_REJECTED", "updated_at": now_iso()}
    else:
        raise HTTPException(400, "Decision must be MATCHED or REJECTED")
    await db.source_listings.update_one({"id": review["source_listing_id"]}, {"$set": listing_patch})
    await db.property_match_reviews.update_one({"id": review_id}, {"$set": {
        "status": decision, "resolved_master_property_id": master_property_id if decision == "MATCHED" else None,
        "resolved_by": user["id"], "resolved_at": now_iso(), "updated_at": now_iso(),
    }})
    return {"ok": True, "decision": decision, "master_property_id": listing_patch["master_property_id"]}


@router.post("/admin/market/listings/{source_listing_id}/rematch")
async def rematch_market_listing(source_listing_id: str, user: dict = Depends(require_staff)):
    listing = await db.source_listings.find_one({"id": source_listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(404, "Source listing not found")
    observation = await db.source_listing_observations.find_one(
        {"source_listing_id": source_listing_id}, {"_id": 0}, sort=[("observed_at", -1)]
    )
    if not observation:
        raise HTTPException(409, "Source listing has no observation to rematch")
    match = await service.match_master(observation)
    await db.source_listings.update_one({"id": source_listing_id}, {"$set": {
        "master_property_id": match["master_property_id"],
        "match_status": match["status"],
        "match_confidence": match["confidence"],
        "match_rule": match["rule"],
        "updated_at": now_iso(),
    }})
    return match
