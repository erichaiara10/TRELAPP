"""Staff-only Property Data Aggregation and Master Property link endpoints."""
import statistics
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query

from core.account_policy import account_category
from core.collectors import get_collector, registered as registered_collectors
from core.collectors.discovery import discover_listing_pages
from core.collectors.selector_tester import collector_defaults, probe_collector
from core.comparable_evidence import ComparableEvidenceService
from core.db import db, new_id, now_iso
from core.market_property_link import MarketPropertyLinkService, collector_payload
from core.security import get_current_user
from models import MarketObservationCreate

router = APIRouter()
service = MarketPropertyLinkService(db)
price_guidance = ComparableEvidenceService(db)


async def require_staff(user: dict = Depends(get_current_user)) -> dict:
    if account_category(user) != "STAFF" or user.get("status", "ACTIVE") != "ACTIVE":
        raise HTTPException(403, "Staff account required")
    return user


def _source_view(row: dict) -> dict:
    item = dict(row)
    item["collector"] = item.get("collector_key")
    item["source_id"] = item.get("id")
    item.setdefault("collection_frequency", "manual")
    item.setdefault("allow_source_auto_match", True)
    item.setdefault("parser_version", "1.0")
    return item


def _domain(payload: dict) -> str:
    raw = str(payload.get("domain") or "").strip().lower()
    if raw:
        return raw.removeprefix("www.")
    base = str(payload.get("base_url") or "").strip()
    return (urlparse(base if "://" in base else f"https://{base}").hostname or "").lower().removeprefix("www.")


@router.get("/admin/market/sources")
async def list_sources(user: dict = Depends(require_staff)):
    rows = await db.source_sites.find({}, {"_id": 0}).sort("name", 1).to_list(500)
    return [_source_view(row) for row in rows]


@router.post("/admin/market/sources")
async def create_source(payload: dict, user: dict = Depends(require_staff)):
    domain = _domain(payload)
    if not str(payload.get("name") or "").strip() or not domain:
        raise HTTPException(400, "Source name and base URL are required")
    if await db.source_sites.find_one({"domain": domain}, {"_id": 0, "id": 1}):
        raise HTTPException(409, "Source domain already exists")
    timestamp = now_iso()
    document = {
        "id": new_id(), "name": str(payload["name"]).strip(), "domain": domain,
        "base_url": payload.get("base_url") or f"https://{domain}",
        "description": payload.get("description"), "active": bool(payload.get("active", True)),
        "is_trel_owned": bool(payload.get("is_trel_owned", False)),
        "collector_key": payload.get("collector") or payload.get("collector_key") or "generic_web",
        "collection_frequency": payload.get("collection_frequency") or "manual",
        "allow_source_auto_match": bool(payload.get("allow_source_auto_match", True)),
        "parser_version": payload.get("parser_version") or "1.0",
        "listing_pages": payload.get("listing_pages") or [],
        "parser_config": payload.get("parser_config") or {},
        "created_at": timestamp, "updated_at": timestamp,
    }
    await db.source_sites.insert_one(document)
    document.pop("_id", None)
    return _source_view(document)


@router.put("/admin/market/sources/{source_site_id}")
async def update_source(source_site_id: str, payload: dict, user: dict = Depends(require_staff)):
    existing = await db.source_sites.find_one({"id": source_site_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Source not found")
    patch = dict(payload)
    if "collector" in patch:
        patch["collector_key"] = patch.pop("collector")
    patch["domain"] = _domain({**existing, **patch})
    patch["updated_at"] = now_iso()
    patch.pop("id", None)
    await db.source_sites.update_one({"id": source_site_id}, {"$set": patch})
    return _source_view({**existing, **patch})


@router.delete("/admin/market/sources/{source_site_id}")
async def delete_source(source_site_id: str, user: dict = Depends(require_staff)):
    result = await db.source_sites.delete_one({"id": source_site_id})
    if not result.deleted_count:
        raise HTTPException(404, "Source not found")
    return {"ok": True}


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
    await db.source_sites.update_one({"id": source_site_id}, {"$set": {"last_run_at": run["finished_at"], "updated_at": now_iso()}})
    run.pop("_id", None)
    return _run_view(run)


def _run_view(row: dict) -> dict:
    item = dict(row)
    item["source_id"] = item.get("source_site_id")
    item["listings_seen"] = item.get("records_seen", 0)
    item["listings_new"] = item.get("records_ingested", 0)
    item["listings_updated"] = 0
    item["matches_created"] = item.get("records_matched", 0)
    item["review_cases_created"] = item.get("records_review_required", 0)
    item["status"] = str(item.get("status") or "").lower()
    return item


@router.get("/admin/market/runs")
async def list_runs(source_id: str = None, limit: int = 100, user: dict = Depends(require_staff)):
    query = {"source_site_id": source_id} if source_id else {}
    rows = await db.collection_runs.find(query, {"_id": 0}).sort("started_at", -1).limit(limit).to_list(limit)
    return [_run_view(row) for row in rows]


@router.get("/admin/market/sources/health")
async def source_health(user: dict = Depends(require_staff)):
    sources = await db.source_sites.find({}, {"_id": 0}).to_list(500)
    result = []
    for source in sources:
        runs = await db.collection_runs.find({"source_site_id": source["id"]}, {"_id": 0}).sort("started_at", -1).limit(10).to_list(10)
        successes = sum(1 for run in runs if run.get("status") == "SUCCESS")
        result.append({"source_id": source["id"], "runs": len(runs), "success_rate": round(successes * 100 / len(runs), 1) if runs else None,
                       "consecutive_failures": next((index for index, run in enumerate(runs) if run.get("status") == "SUCCESS"), len(runs))})
    return result


@router.get("/admin/market/collectors")
async def list_collectors(user: dict = Depends(require_staff)):
    return [{**item, "default_config": collector_defaults(item["key"])} for item in registered_collectors()]


@router.get("/admin/market/collectors/{key}/defaults")
async def get_collector_defaults(key: str, user: dict = Depends(require_staff)):
    defaults = collector_defaults(key)
    if defaults is None:
        raise HTTPException(404, "Collector defaults not found")
    return {"collector": key, "default_config": defaults}


@router.post("/admin/market/collectors/{key}/discover")
async def discover_source_pages(key: str, payload: dict, user: dict = Depends(require_staff)):
    return await discover_listing_pages(payload.get("base_url"), key, payload.get("parser_config"))


@router.post("/admin/market/collectors/{key}/test")
async def test_collector(key: str, payload: dict, user: dict = Depends(require_staff)):
    return await probe_collector(key, payload.get("url"), payload.get("selectors"))


@router.post("/admin/market/sources/{source_site_id}/parser-config")
async def save_parser_config(source_site_id: str, payload: dict, user: dict = Depends(require_staff)):
    source = await db.source_sites.find_one({"id": source_site_id}, {"_id": 0})
    if not source:
        raise HTTPException(404, "Source not found")
    merged = {**(source.get("parser_config") or {}), **(payload.get("parser_config") or {})}
    await db.source_sites.update_one({"id": source_site_id}, {"$set": {"parser_config": merged, "updated_at": now_iso()}})
    return {"ok": True, "parser_config": merged}


@router.post("/admin/market/sources/rediscover-all")
async def rediscover_all(user: dict = Depends(require_staff)):
    rows = await list_sources(user)
    diffs = []
    for source in rows:
        if not source.get("base_url") or not source.get("collector"):
            continue
        discovered = await discover_listing_pages(source["base_url"], source["collector"], source.get("parser_config"))
        suggested = discovered.get("candidates") or []
        old_urls = {p.get("listing_url") for p in source.get("listing_pages") or []}
        new_urls = {p.get("listing_url") for p in suggested}
        diffs.append({"source_id": source["id"], "source_name": source["name"], "base_url": source.get("base_url"),
                      "existing": source.get("listing_pages") or [], "suggested": suggested,
                      "added": sorted(new_urls - old_urls), "removed": sorted(old_urls - new_urls),
                      "changed": old_urls != new_urls})
    return {"total": len(rows), "diffs": diffs}


@router.put("/admin/market/sources/{source_site_id}/listing-pages")
async def save_listing_pages(source_site_id: str, payload: dict, user: dict = Depends(require_staff)):
    pages = payload.get("listing_pages") or payload.get("pages") or []
    result = await db.source_sites.update_one({"id": source_site_id}, {"$set": {"listing_pages": pages, "updated_at": now_iso()}})
    if not result.matched_count:
        raise HTTPException(404, "Source not found")
    return {"ok": True, "listing_pages": pages}


@router.get("/admin/market/listings")
async def list_market_listings(limit: int = Query(default=100, ge=1, le=500), user: dict = Depends(require_staff)):
    return await service.list_evidence(limit)


@router.get("/admin/market/summary")
async def market_summary(user: dict = Depends(require_staff)):
    summary = await service.summary()
    summary.update({
        "sources": await db.source_sites.count_documents({}),
        "active_sources": await db.source_sites.count_documents({"active": True}),
        "market_listings": await db.source_listings.count_documents({}),
        "active_listings": await db.source_listings.count_documents({"current_status": "ACTIVE"}),
        "matches_active": await db.source_listings.count_documents({"match_status": "MATCHED"}),
        "review_cases_open": await db.property_match_reviews.count_documents({"status": "OPEN"}),
        "audit_events": await db.audit_events.count_documents({"subject_type": {"$in": ["source_listing", "market_source", "property_match"]}}),
    })
    return summary


@router.get("/admin/market/matches")
async def list_matches(status: str = "active", limit: int = 100, user: dict = Depends(require_staff)):
    rows = await db.source_listings.find({"match_status": "MATCHED"}, {"_id": 0}).sort("updated_at", -1).limit(limit).to_list(limit)
    return [{"id": row["id"], "market_listing_id": row["id"], "master_property_id": row.get("master_property_id"),
             "status": "active", "method": row.get("match_rule"), "decision_band": "confirmed",
             "score": row.get("match_confidence", 0), "created_at": row.get("created_at"), "updated_at": row.get("updated_at")} for row in rows]


@router.post("/admin/market/matches/{match_id}/detach")
async def detach_match(match_id: str, payload: dict = None, user: dict = Depends(require_staff)):
    result = await db.source_listings.update_one({"id": match_id}, {"$set": {"master_property_id": None, "match_status": "UNMATCHED", "match_confidence": 0, "match_rule": "STAFF_DETACHED", "updated_at": now_iso()}})
    if not result.matched_count:
        raise HTTPException(404, "Match not found")
    return {"ok": True}


@router.get("/admin/market/match-reviews")
async def list_match_reviews(user: dict = Depends(require_staff)):
    return await db.property_match_reviews.find({"status": "OPEN"}, {"_id": 0}).sort("created_at", 1).to_list(500)


@router.get("/admin/market/review-cases")
async def list_review_cases(status: str = "open", case_type: str = None, limit: int = 100, user: dict = Depends(require_staff)):
    query = {"status": status.upper()}
    rows = await db.property_match_reviews.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    return [{**row, "status": str(row.get("status") or "").lower(), "case_type": row.get("case_type") or "possible"} for row in rows]


@router.put("/admin/market/review-cases/{review_id}")
async def update_review_case(review_id: str, payload: dict, user: dict = Depends(require_staff)):
    patch = {**payload, "status": str(payload.get("status") or "open").upper(), "updated_at": now_iso()}
    result = await db.property_match_reviews.update_one({"id": review_id}, {"$set": patch})
    if not result.matched_count:
        raise HTTPException(404, "Review case not found")
    return {"ok": True}


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
        listing_patch = {"master_property_id": master_property_id, "match_status": "MATCHED", "match_confidence": 100, "match_rule": "STAFF_REVIEW", "updated_at": now_iso()}
    elif decision == "REJECTED":
        listing_patch = {"master_property_id": None, "match_status": "UNMATCHED", "match_confidence": 0, "match_rule": "STAFF_REJECTED", "updated_at": now_iso()}
    else:
        raise HTTPException(400, "Decision must be MATCHED or REJECTED")
    await db.source_listings.update_one({"id": review["source_listing_id"]}, {"$set": listing_patch})
    await db.property_match_reviews.update_one({"id": review_id}, {"$set": {"status": decision, "resolved_by": user["id"], "resolved_at": now_iso(), "updated_at": now_iso()}})
    return {"ok": True, "decision": decision}


@router.post("/admin/market/listings/{source_listing_id}/rematch")
async def rematch_market_listing(source_listing_id: str, user: dict = Depends(require_staff)):
    listing = await db.source_listings.find_one({"id": source_listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(404, "Source listing not found")
    observation = await db.source_listing_observations.find_one({"source_listing_id": source_listing_id}, {"_id": 0}, sort=[("observed_at", -1)])
    if not observation:
        raise HTTPException(409, "Source listing has no observation to rematch")
    match = await service.match_master(observation)
    await db.source_listings.update_one({"id": source_listing_id}, {"$set": {"master_property_id": match["master_property_id"], "match_status": match["status"], "match_confidence": match["confidence"], "match_rule": match["rule"], "updated_at": now_iso()}})
    return match


async def _priced_rows(purpose: str):
    transaction = "RENT" if purpose == "rent" else "SALE"
    observations = await db.source_listing_observations.find({"transaction_type": transaction, "priced_usable": True, "comparable_eligible": True}, {"_id": 0}).to_list(5000)
    ids = [row["id"] for row in observations]
    prices = await db.observation_prices.find({"observation_id": {"$in": ids}}, {"_id": 0}).to_list(len(ids)) if ids else []
    by_id = {row["observation_id"]: row for row in prices}
    return [(row, by_id.get(row["id"], {})) for row in observations if by_id.get(row["id"], {}).get("amount") is not None]


@router.get("/admin/market/analytics/price-trends")
async def price_trends(purpose: str = "sale", months: int = 12, user: dict = Depends(require_staff)):
    cutoff = datetime.now(timezone.utc) - timedelta(days=months * 31)
    buckets = {}
    for row, price in await _priced_rows(purpose):
        try:
            observed = datetime.fromisoformat(str(row.get("observed_at") or "").replace("Z", "+00:00"))
            if observed.tzinfo is None:
                observed = observed.replace(tzinfo=timezone.utc)
            if observed < cutoff:
                continue
            buckets.setdefault(observed.strftime("%Y-%m"), []).append(float(price["amount"]))
        except Exception:
            continue
    return [{"month": key, "count": len(values), "median": statistics.median(values)} for key, values in sorted(buckets.items())]


@router.get("/admin/market/analytics/median-by-suburb")
async def median_by_suburb(purpose: str = "sale", limit: int = 12, user: dict = Depends(require_staff)):
    grouped = {}
    for row, price in await _priced_rows(purpose):
        suburb = str(row.get("suburb_name") or "").strip()
        if suburb:
            grouped.setdefault(suburb, []).append(float(price["amount"]))
    result = [{"suburb": key, "count": len(values), "median": statistics.median(values)} for key, values in grouped.items()]
    return sorted(result, key=lambda item: item["median"], reverse=True)[:limit]


@router.get("/admin/market/analytics/heatmap")
async def heatmap(purpose: str = "sale", months: int = 12, user: dict = Depends(require_staff)):
    trend = await price_trends(purpose, months, user)
    return {"months": [row["month"] for row in trend], "suburbs": [], "cells": []}


@router.get("/admin/market/analytics/source-strip")
async def source_strip(user: dict = Depends(require_staff)):
    return await source_health(user)


@router.get("/admin/market/analytics/quick-insights")
async def quick_insights(user: dict = Depends(require_staff)):
    return {"by_class": [], "by_purpose": [], "match_bands": []}


@router.post("/admin/market/guidance/run")
async def run_guidance(payload: dict, user: dict = Depends(require_staff)):
    request_payload = {
        "property_id": payload.get("property_id"), "property_type": payload.get("property_subtype") or payload.get("property_class") or "House",
        "listing_type": payload.get("purpose") or "sale", "price": float(payload.get("subject_asking_price") or 1),
        "province": payload.get("province"), "city": payload.get("city") or payload.get("suburb"),
        "suburb": payload.get("suburb"), "local_area": payload.get("local_area"),
        "bedrooms": payload.get("bedrooms"), "bathrooms": payload.get("bathrooms"),
        "land_area_sqm": payload.get("land_area_m2"), "building_area_sqm": payload.get("building_area_m2"),
    }
    result = await price_guidance.analyse(request_payload)
    wrapper = {"id": new_id(), "created_at": now_iso(), "outputs": {"workflow": payload.get("workflow") or "admin"}, **result}
    await db.system_settings.update_one({"id": f"guidance:{wrapper['id']}"}, {"$set": wrapper}, upsert=True)
    return {"result": wrapper, "comparables": result.get("comparables") or []}


@router.get("/admin/market/guidance/results")
async def guidance_results(limit: int = 50, user: dict = Depends(require_staff)):
    return await db.system_settings.find({"id": {"$regex": "^guidance:"}}, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)


@router.get("/admin/market/guidance/results/{result_id}")
async def guidance_result(result_id: str, user: dict = Depends(require_staff)):
    row = await db.system_settings.find_one({"$or": [{"id": result_id}, {"id": f"guidance:{result_id}"}]}, {"_id": 0})
    if not row:
        raise HTTPException(404, "Guidance result not found")
    return {"result": row, "comparables": row.get("comparables") or []}


@router.get("/admin/market/audit-events")
async def audit_events(entity_type: str = None, event_type: str = None, limit: int = 200, user: dict = Depends(require_staff)):
    query = {}
    if entity_type:
        query["subject_type"] = entity_type
    if event_type:
        query["action"] = event_type
    return await db.audit_events.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)


@router.get("/admin/market/config")
async def list_config(user: dict = Depends(require_staff)):
    return await db.system_settings.find({"kind": "market_configuration"}, {"_id": 0}).sort("created_at", -1).to_list(100)


@router.get("/admin/market/config/active")
async def active_config(algorithm: str = "combined", user: dict = Depends(require_staff)):
    return await db.system_settings.find_one({"kind": "market_configuration", "active": True}, {"_id": 0})


@router.post("/admin/market/config")
async def create_config(payload: dict, user: dict = Depends(require_staff)):
    row = {"id": new_id(), "kind": "market_configuration", "active": False, "created_at": now_iso(), **payload}
    await db.system_settings.insert_one(row)
    row.pop("_id", None)
    return row


@router.post("/admin/market/config/{config_id}/activate")
async def activate_config(config_id: str, user: dict = Depends(require_staff)):
    await db.system_settings.update_many({"kind": "market_configuration"}, {"$set": {"active": False}})
    result = await db.system_settings.update_one({"id": config_id, "kind": "market_configuration"}, {"$set": {"active": True, "activated_at": now_iso()}})
    if not result.matched_count:
        raise HTTPException(404, "Configuration not found")
    return {"ok": True}


@router.get("/admin/market/retention/preview")
async def retention_preview(user: dict = Depends(require_staff)):
    return {"source_listings": 0, "observations": 0, "message": "No records are removed automatically."}


@router.post("/admin/market/retention/run")
async def retention_run(user: dict = Depends(require_staff)):
    return {"ok": True, "removed": 0}


@router.get("/admin/market/scheduler")
async def scheduler(user: dict = Depends(require_staff)):
    return await db.system_settings.find_one({"id": "market_scheduler"}, {"_id": 0}) or {"id": "market_scheduler", "paused": False}


@router.post("/admin/market/scheduler/pause")
async def toggle_scheduler(payload: dict, user: dict = Depends(require_staff)):
    row = {"id": "market_scheduler", "paused": bool(payload.get("paused")), "updated_at": now_iso()}
    await db.system_settings.update_one({"id": "market_scheduler"}, {"$set": row}, upsert=True)
    return row
