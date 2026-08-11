"""Market Intelligence — Phase 1 skeleton routes.

Implements CRUD/listing endpoints for the data-aggregation identity graph
(sources, runs, listings, master properties, units, matches, review cases,
audit events, configuration, location reference).

Matching/guidance engine execution is intentionally NOT wired here — that
lands in Phase B (matching) and Phase C (guidance). Every write to a
configuration or manual-override emits a `market_audit_events` row.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from core.db import db, new_id, now_iso, strip_id
from core.security import get_current_user
from models import (
    CollectionRun,
    LocationReference,
    MarketAuditEvent,
    MarketConfiguration,
    MarketConfigurationCreate,
    MarketListing,
    MarketReviewCase,
    MarketSource,
    MarketSourceCreate,
    MasterProperty,
    MasterPropertyCreate,
    PropertyMatch,
    PropertyUnit,
    PropertyUnitCreate,
)

router = APIRouter()


# ---------------- helpers ----------------
async def _audit(event_type: str, actor: dict, *, entity_type=None, entity_id=None,
                 payload=None, reason=None):
    ev = MarketAuditEvent(
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload or {},
        reason=reason,
        actor_id=(actor or {}).get("id"),
    ).model_dump()
    await db.market_audit_events.insert_one(ev)


async def _active_config_version() -> Optional[str]:
    cfg = await db.market_configuration.find_one({"active": True}, {"_id": 0, "version": 1})
    return (cfg or {}).get("version")


# ============================================================
# MARKET SOURCES
# ============================================================
@router.get("/admin/market/sources")
async def list_sources(user: dict = Depends(get_current_user)):
    return await db.market_sources.find({}, {"_id": 0}).sort("name", 1).to_list(500)


@router.post("/admin/market/sources")
async def create_source(payload: MarketSourceCreate, user: dict = Depends(get_current_user)):
    if await db.market_sources.find_one({"name": payload.name}):
        raise HTTPException(400, "A source with this name already exists")
    doc = MarketSource(**payload.model_dump()).model_dump()
    await db.market_sources.insert_one(doc)
    await _audit("source_created", user, entity_type="market_source", entity_id=doc["id"],
                 payload={"name": doc["name"]})
    return strip_id(doc)


@router.put("/admin/market/sources/{sid}")
async def update_source(sid: str, payload: dict, user: dict = Depends(get_current_user)):
    payload.pop("id", None); payload.pop("_id", None)
    payload["updated_at"] = now_iso()
    res = await db.market_sources.update_one({"id": sid}, {"$set": payload})
    if res.matched_count == 0:
        raise HTTPException(404, "Source not found")
    await _audit("source_updated", user, entity_type="market_source", entity_id=sid,
                 payload=payload)
    return await db.market_sources.find_one({"id": sid}, {"_id": 0})


@router.delete("/admin/market/sources/{sid}")
async def delete_source(sid: str, user: dict = Depends(get_current_user)):
    r = await db.market_sources.delete_one({"id": sid})
    if r.deleted_count == 0:
        raise HTTPException(404, "Source not found")
    await _audit("source_deleted", user, entity_type="market_source", entity_id=sid)
    return {"ok": True}


# ============================================================
# COLLECTION RUNS
# ============================================================
@router.get("/admin/market/runs")
async def list_runs(source_id: Optional[str] = None, limit: int = 100,
                    user: dict = Depends(get_current_user)):
    q = {"source_id": source_id} if source_id else {}
    return await db.collection_runs.find(q, {"_id": 0}).sort("started_at", -1).to_list(limit)


# ============================================================
# MARKET LISTINGS
# ============================================================
@router.get("/admin/market/listings")
async def list_listings(source_id: Optional[str] = None, suburb: Optional[str] = None,
                        status: Optional[str] = None, limit: int = 100,
                        user: dict = Depends(get_current_user)):
    q: dict = {}
    if source_id: q["source_id"] = source_id
    if suburb:    q["suburb"] = suburb
    if status:    q["status"] = status
    return await db.market_listings.find(q, {"_id": 0}).sort("last_seen", -1).to_list(limit)


@router.get("/admin/market/listings/{lid}")
async def get_listing(lid: str, user: dict = Depends(get_current_user)):
    doc = await db.market_listings.find_one({"id": lid}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Listing not found")
    return doc


# ============================================================
# MASTER PROPERTIES
# ============================================================
@router.get("/admin/market/master-properties")
async def list_masters(suburb: Optional[str] = None, property_class: Optional[str] = None,
                       trel_property_id: Optional[str] = None,
                       q: Optional[str] = None, limit: int = 100,
                       user: dict = Depends(get_current_user)):
    query: dict = {}
    if suburb:            query["suburb"] = suburb
    if property_class:    query["property_class"] = property_class
    if trel_property_id:  query["trel_property_id"] = trel_property_id
    if q:
        query["$or"] = [{f: {"$regex": q, "$options": "i"}}
                        for f in ("suburb", "street", "building_name", "lot_number", "portion_number")]
    return await db.master_properties.find(query, {"_id": 0}).sort("updated_at", -1).to_list(limit)


@router.get("/admin/market/master-properties/{mid}")
async def get_master(mid: str, user: dict = Depends(get_current_user)):
    doc = await db.master_properties.find_one({"id": mid}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Master property not found")
    return doc


@router.post("/admin/market/master-properties")
async def create_master(payload: MasterPropertyCreate, user: dict = Depends(get_current_user)):
    doc = MasterProperty(**payload.model_dump()).model_dump()
    await db.master_properties.insert_one(doc)
    await _audit("master_created", user, entity_type="master_property", entity_id=doc["id"])
    return strip_id(doc)


@router.put("/admin/market/master-properties/{mid}")
async def update_master(mid: str, payload: dict, user: dict = Depends(get_current_user)):
    payload.pop("id", None); payload.pop("_id", None)
    payload["updated_at"] = now_iso()
    res = await db.master_properties.update_one({"id": mid}, {"$set": payload})
    if res.matched_count == 0:
        raise HTTPException(404, "Master property not found")
    await _audit("master_updated", user, entity_type="master_property", entity_id=mid,
                 payload=payload)
    return await db.master_properties.find_one({"id": mid}, {"_id": 0})


# ============================================================
# PROPERTY UNITS
# ============================================================
@router.get("/admin/market/property-units")
async def list_units(master_property_id: Optional[str] = None, limit: int = 200,
                     user: dict = Depends(get_current_user)):
    q = {"master_property_id": master_property_id} if master_property_id else {}
    return await db.property_units.find(q, {"_id": 0}).sort("created_at", -1).to_list(limit)


@router.post("/admin/market/property-units")
async def create_unit(payload: PropertyUnitCreate, user: dict = Depends(get_current_user)):
    if not await db.master_properties.find_one({"id": payload.master_property_id}):
        raise HTTPException(400, "Parent master property not found")
    doc = PropertyUnit(**payload.model_dump()).model_dump()
    await db.property_units.insert_one(doc)
    await _audit("unit_created", user, entity_type="property_unit", entity_id=doc["id"],
                 payload={"master_property_id": doc["master_property_id"]})
    return strip_id(doc)


@router.put("/admin/market/property-units/{uid}")
async def update_unit(uid: str, payload: dict, user: dict = Depends(get_current_user)):
    payload.pop("id", None); payload.pop("_id", None)
    payload["updated_at"] = now_iso()
    res = await db.property_units.update_one({"id": uid}, {"$set": payload})
    if res.matched_count == 0:
        raise HTTPException(404, "Property unit not found")
    await _audit("unit_updated", user, entity_type="property_unit", entity_id=uid,
                 payload=payload)
    return await db.property_units.find_one({"id": uid}, {"_id": 0})


# ============================================================
# PROPERTY MATCHES
# ============================================================
@router.get("/admin/market/matches")
async def list_matches(market_listing_id: Optional[str] = None,
                       master_property_id: Optional[str] = None,
                       status: Optional[str] = "active",
                       limit: int = 200,
                       user: dict = Depends(get_current_user)):
    q: dict = {}
    if market_listing_id:   q["market_listing_id"] = market_listing_id
    if master_property_id:  q["master_property_id"] = master_property_id
    if status:              q["status"] = status
    return await db.property_matches.find(q, {"_id": 0}).sort("created_at", -1).to_list(limit)


@router.post("/admin/market/matches/{match_id}/detach")
async def detach_match(match_id: str, payload: dict = None,
                       user: dict = Depends(get_current_user)):
    reason = (payload or {}).get("reason") or "manual detach"
    res = await db.property_matches.update_one(
        {"id": match_id, "status": "active"},
        {"$set": {"status": "detached", "reviewer_id": user.get("id"),
                  "reviewer_note": reason, "updated_at": now_iso()}},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Active match not found")
    await _audit("match_detached", user, entity_type="property_match", entity_id=match_id,
                 reason=reason)
    return {"ok": True}


# ============================================================
# REVIEW CASES
# ============================================================
@router.get("/admin/market/review-cases")
async def list_review_cases(status: Optional[str] = "open", case_type: Optional[str] = None,
                            limit: int = 100, user: dict = Depends(get_current_user)):
    q: dict = {}
    if status:    q["status"] = status
    if case_type: q["case_type"] = case_type
    return await db.market_review_cases.find(q, {"_id": 0}).sort("created_at", -1).to_list(limit)


@router.put("/admin/market/review-cases/{cid}")
async def update_review_case(cid: str, payload: dict, user: dict = Depends(get_current_user)):
    payload.pop("id", None); payload.pop("_id", None)
    payload["updated_at"] = now_iso()
    payload["reviewer_id"] = user.get("id")
    res = await db.market_review_cases.update_one({"id": cid}, {"$set": payload})
    if res.matched_count == 0:
        raise HTTPException(404, "Review case not found")
    await _audit("review_case_updated", user, entity_type="market_review_case", entity_id=cid,
                 payload=payload)
    return await db.market_review_cases.find_one({"id": cid}, {"_id": 0})


# ============================================================
# AUDIT EVENTS (read-only)
# ============================================================
@router.get("/admin/market/audit-events")
async def list_audit_events(entity_type: Optional[str] = None,
                            entity_id: Optional[str] = None,
                            limit: int = 200,
                            user: dict = Depends(get_current_user)):
    q: dict = {}
    if entity_type: q["entity_type"] = entity_type
    if entity_id:   q["entity_id"] = entity_id
    return await db.market_audit_events.find(q, {"_id": 0}).sort("created_at", -1).to_list(limit)


# ============================================================
# MARKET CONFIGURATION (versioned)
# ============================================================
@router.get("/admin/market/config")
async def list_configs(user: dict = Depends(get_current_user)):
    return await db.market_configuration.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)


@router.get("/admin/market/config/active")
async def get_active_config(algorithm: str = Query("combined"),
                            user: dict = Depends(get_current_user)):
    doc = await db.market_configuration.find_one(
        {"active": True, "algorithm": algorithm}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(404, "No active configuration for this algorithm")
    return doc


@router.post("/admin/market/config")
async def create_config(payload: MarketConfigurationCreate,
                        user: dict = Depends(get_current_user)):
    if await db.market_configuration.find_one(
        {"version": payload.version, "algorithm": payload.algorithm}
    ):
        raise HTTPException(400, "This version already exists for that algorithm")
    doc = MarketConfiguration(
        version=payload.version, algorithm=payload.algorithm,
        parameters=payload.parameters, notes=payload.notes or "",
        active=bool(payload.activate), created_by=user.get("id"),
    ).model_dump()
    if payload.activate:
        await db.market_configuration.update_many(
            {"algorithm": payload.algorithm, "active": True},
            {"$set": {"active": False}},
        )
    await db.market_configuration.insert_one(doc)
    await _audit("config_created", user, entity_type="market_configuration",
                 entity_id=doc["id"],
                 payload={"version": doc["version"], "algorithm": doc["algorithm"],
                          "activated": payload.activate})
    return strip_id(doc)


@router.post("/admin/market/config/{cid}/activate")
async def activate_config(cid: str, user: dict = Depends(get_current_user)):
    doc = await db.market_configuration.find_one({"id": cid}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Configuration not found")
    await db.market_configuration.update_many(
        {"algorithm": doc["algorithm"], "active": True},
        {"$set": {"active": False}},
    )
    await db.market_configuration.update_one({"id": cid}, {"$set": {"active": True}})
    await _audit("config_activated", user, entity_type="market_configuration", entity_id=cid,
                 payload={"version": doc["version"], "algorithm": doc["algorithm"]})
    return await db.market_configuration.find_one({"id": cid}, {"_id": 0})


# ============================================================
# LOCATION REFERENCE (canonical hierarchy + aliases)
# ============================================================
@router.get("/admin/market/location-reference")
async def list_location_reference(province: Optional[str] = None, city: Optional[str] = None,
                                  suburb: Optional[str] = None, limit: int = 1000,
                                  user: dict = Depends(get_current_user)):
    q: dict = {}
    if province: q["province"] = province
    if city:     q["city"] = city
    if suburb:   q["suburb"] = suburb
    return await db.location_reference.find(q, {"_id": 0}).sort([
        ("province", 1), ("city", 1), ("suburb", 1), ("local_area", 1), ("street", 1),
    ]).to_list(limit)


@router.post("/admin/market/location-reference")
async def create_location_reference(payload: dict, user: dict = Depends(get_current_user)):
    doc = LocationReference(**payload).model_dump()
    await db.location_reference.insert_one(doc)
    await _audit("location_reference_added", user, entity_type="location_reference",
                 entity_id=doc["id"], payload=payload)
    return strip_id(doc)


# ============================================================
# DASHBOARD SUMMARY
# ============================================================
@router.get("/admin/market/summary")
async def market_summary(user: dict = Depends(get_current_user)):
    return {
        "sources": await db.market_sources.count_documents({}),
        "active_sources": await db.market_sources.count_documents({"active": True}),
        "market_listings": await db.market_listings.count_documents({}),
        "active_listings": await db.market_listings.count_documents({"status": "active"}),
        "master_properties": await db.master_properties.count_documents({}),
        "property_units": await db.property_units.count_documents({}),
        "matches_active": await db.property_matches.count_documents({"status": "active"}),
        "review_cases_open": await db.market_review_cases.count_documents({"status": "open"}),
        "audit_events": await db.market_audit_events.count_documents({}),
        "active_config_version": await _active_config_version(),
    }
