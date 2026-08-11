"""Market Intelligence — Phase 1 skeleton routes.

Implements CRUD/listing endpoints for the data-aggregation identity graph
(sources, runs, listings, master properties, units, matches, review cases,
audit events, configuration, location reference).

Matching/guidance engine execution is intentionally NOT wired here — that
lands in Phase B (matching) and Phase C (guidance). Every write to a
configuration or manual-override emits a `market_audit_events` row.
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from core.collectors import get_collector, registered as registered_collectors
from core.collectors.hausples_tester import probe_hausples
from core.db import db, new_id, now_iso, strip_id
from core.guidance import generate_guidance
from core.matcher import ingest_market_listing, rematch_listing
from core.retention import preview_retention, run_retention
from core.runs import collection_run, source_health
from core.scheduler import scheduler_state, set_paused
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


async def _active_config_params() -> dict:
    cfg = await db.market_configuration.find_one({"active": True}, {"_id": 0, "parameters": 1})
    return (cfg or {}).get("parameters") or {}


# ---------------- analytics TTL cache ----------------
# The Overview page repeatedly polls the 5 analytics endpoints; before this
# cache each request scanned market_listings from scratch. A 60-second TTL
# per (endpoint, params) is more than fresh enough (scraper runs are minute-scale)
# and drops per-page DB traffic dramatically when multiple admins are watching.
import time as _time
_ANALYTICS_CACHE: dict[str, tuple[float, object]] = {}
_ANALYTICS_TTL_SEC = 60


def _cache_get(key: str):
    hit = _ANALYTICS_CACHE.get(key)
    if not hit:
        return None
    ts, value = hit
    if _time.time() - ts > _ANALYTICS_TTL_SEC:
        _ANALYTICS_CACHE.pop(key, None)
        return None
    return value


def _cache_set(key: str, value):
    _ANALYTICS_CACHE[key] = (_time.time(), value)


def _cache_bust():
    _ANALYTICS_CACHE.clear()


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


@router.get("/admin/market/retention/preview")
async def retention_preview(user: dict = Depends(get_current_user)):
    """Dry-run: how many rows WOULD be soft-deleted right now, per collection."""
    return await preview_retention()


@router.post("/admin/market/retention/run")
async def force_retention(user: dict = Depends(get_current_user)):
    """Manually trigger the retention pass — otherwise runs once every 24h
    via the scheduler tick."""
    return await run_retention(force=True, actor_id=user.get("id"))


@router.get("/admin/market/scheduler")
async def get_scheduler_state(user: dict = Depends(get_current_user)):
    return scheduler_state()


@router.post("/admin/market/scheduler/pause")
async def toggle_scheduler(payload: dict, user: dict = Depends(get_current_user)):
    set_paused(bool(payload.get("paused")))
    await _audit("scheduler_toggle", user, entity_type="scheduler",
                 payload={"paused": bool(payload.get("paused"))})
    return scheduler_state()



@router.get("/admin/market/collectors")
async def list_collectors(user: dict = Depends(get_current_user)):
    return registered_collectors()


@router.post("/admin/market/collectors/hausples_png/test")
async def hausples_selector_test(payload: dict,
                                  user: dict = Depends(get_current_user)):
    """Selector tester — paste a Hausples search-results URL, get per-selector
    match counts + samples. Optional `selectors` overrides let ops A/B-test
    tweaks before saving them to a source's parser_config."""
    url = (payload or {}).get("url")
    if not url or not url.startswith("http"):
        raise HTTPException(400, "Valid URL required")
    return await probe_hausples(url, (payload or {}).get("selectors"))



@router.post("/admin/market/sources/{sid}/collect")
async def collect_source(sid: str, user: dict = Depends(get_current_user)):
    """One-shot: opens a collection_run, drives the source's configured
    collector, closes the run. Returns the final run doc."""
    source = await db.market_sources.find_one({"id": sid}, {"_id": 0})
    if not source:
        raise HTTPException(404, "Source not found")
    if not source.get("active", True):
        raise HTTPException(400, "Source is paused")
    collector_key = source.get("collector") or "seed"
    Collector = get_collector(collector_key)
    if not Collector:
        raise HTTPException(400, f"Unknown collector '{collector_key}'")

    collector = Collector(source)
    async with collection_run(sid, run_type="manual",
                              triggered_by=user.get("id"),
                              parser_version=source.get("parser_version")) as run:
        async for payload in collector.iter_listings():
            await run.ingest(payload)
        run_id = run.run_id

    doc = await db.collection_runs.find_one({"id": run_id}, {"_id": 0})
    return doc



@router.get("/admin/market/runs")
async def list_runs(source_id: Optional[str] = None, limit: int = 100,
                    user: dict = Depends(get_current_user)):
    q = {"source_id": source_id} if source_id else {}
    return await db.collection_runs.find(q, {"_id": 0}).sort("started_at", -1).to_list(limit)


@router.get("/admin/market/runs/{run_id}")
async def get_run(run_id: str, user: dict = Depends(get_current_user)):
    doc = await db.collection_runs.find_one({"id": run_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Run not found")
    return doc


@router.post("/admin/market/runs/start")
async def start_run(payload: dict, user: dict = Depends(get_current_user)):
    """Manually start a collection run. Returns the new run doc so a client
    can stream listings via POST /runs/{id}/listings and then POST /finish."""
    sid = payload.get("source_id")
    if not sid:
        raise HTTPException(400, "source_id is required")
    source = await db.market_sources.find_one({"id": sid}, {"_id": 0})
    if not source:
        raise HTTPException(404, "Source not found")
    if not source.get("active", True):
        raise HTTPException(400, "Source is paused (active=false)")
    from models import CollectionRun as _CR
    run = _CR(
        source_id=sid,
        run_type=payload.get("run_type") or "manual",
        triggered_by=user.get("id"),
        parser_version=payload.get("parser_version") or source.get("parser_version"),
    ).model_dump()
    await db.collection_runs.insert_one(run)
    run.pop("_id", None)
    await _audit("run_started", user, entity_type="collection_run",
                 entity_id=run["id"], payload={"source_id": sid})
    await db.market_sources.update_one(
        {"id": sid}, {"$set": {"last_run_at": run["started_at"], "updated_at": now_iso()}},
    )
    return run


@router.post("/admin/market/runs/{run_id}/listings")
async def ingest_batch(run_id: str, payload: dict, user: dict = Depends(get_current_user)):
    """Batch ingest listings under an open run. `payload = {"listings":[{…}, …]}`.
    Each item runs the MATCH-1.0 pipeline; per-item errors are captured on the
    run doc without stopping the batch."""
    run = await db.collection_runs.find_one({"id": run_id}, {"_id": 0})
    if not run:
        raise HTTPException(404, "Run not found")
    if run["status"] != "running":
        raise HTTPException(400, f"Run is {run['status']} — cannot ingest more")
    items = payload.get("listings") or []
    if not isinstance(items, list) or not items:
        raise HTTPException(400, "listings must be a non-empty array")

    # Reuse the RunContext logic to keep counters/errors consistent
    from core.runs import RunContext
    ctx = RunContext(run_id, run["source_id"], user.get("id"))
    ctx.seen = int(run.get("listings_seen", 0))
    ctx.new = int(run.get("listings_new", 0))
    ctx.updated = int(run.get("listings_updated", 0))
    ctx.matches = int(run.get("matches_created", 0))
    ctx.review_cases = int(run.get("review_cases_created", 0))
    ctx.errors = list(run.get("errors") or [])

    results = []
    for item in items:
        r = await ctx.ingest(item)
        results.append({"source_listing_id": item.get("source_listing_id"),
                        "matched": bool(r.get("match")),
                        "review_case": bool(r.get("review_case")),
                        "error": r.get("error")})

    return {"run_id": run_id, "processed": len(items),
            "seen": ctx.seen, "new": ctx.new, "updated": ctx.updated,
            "matches": ctx.matches, "review_cases": ctx.review_cases,
            "errors": len(ctx.errors), "results": results}


@router.post("/admin/market/runs/{run_id}/finish")
async def finish_run(run_id: str, payload: Optional[dict] = None,
                     user: dict = Depends(get_current_user)):
    run = await db.collection_runs.find_one({"id": run_id}, {"_id": 0})
    if not run:
        raise HTTPException(404, "Run not found")
    if run["status"] != "running":
        raise HTTPException(400, f"Run already {run['status']}")

    forced = (payload or {}).get("status")     # "success" | "failed" | None
    err_msg = (payload or {}).get("error")
    if err_msg:
        run["errors"] = (run.get("errors") or []) + [str(err_msg)[:500]]

    status = forced or ("success" if not run.get("errors")
                        else ("failed" if forced == "failed" else "partial"))
    if status not in ("success", "failed", "partial"):
        raise HTTPException(400, "status must be success|failed|partial")

    try:
        started = datetime.fromisoformat(run["started_at"].replace("Z", "+00:00"))
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        duration_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
    except Exception:
        duration_ms = None

    finished = now_iso()
    await db.collection_runs.update_one(
        {"id": run_id},
        {"$set": {"finished_at": finished, "duration_ms": duration_ms,
                  "status": status, "errors": run.get("errors") or []}},
    )
    # Update source health
    sid = run["source_id"]
    patch = {"last_run_at": finished, "updated_at": now_iso()}
    if status == "success":
        patch["last_successful_run_at"] = finished
        patch["consecutive_failures"] = 0
    elif status == "failed":
        src = await db.market_sources.find_one({"id": sid}, {"_id": 0}) or {}
        patch["consecutive_failures"] = int(src.get("consecutive_failures", 0)) + 1
    await db.market_sources.update_one({"id": sid}, {"$set": patch})
    await _audit(f"run_{status}", user, entity_type="collection_run",
                 entity_id=run_id,
                 payload={"source_id": sid, "duration_ms": duration_ms,
                          "seen": run.get("listings_seen"),
                          "errors": len(run.get("errors") or [])})
    return await db.collection_runs.find_one({"id": run_id}, {"_id": 0})


# ============================================================
# SOURCE HEALTH
# ============================================================
@router.get("/admin/market/sources/health")
async def sources_health(window: int = 10, user: dict = Depends(get_current_user)):
    sources = await db.market_sources.find({}, {"_id": 0}).sort("name", 1).to_list(500)
    out = []
    for s in sources:
        h = await source_health(s["id"], window=window)
        out.append({**s, **h})
    return out


# ============================================================
# LISTING SNAPSHOTS
# ============================================================
@router.get("/admin/market/listings/{lid}/snapshots")
async def list_listing_snapshots(lid: str, user: dict = Depends(get_current_user)):
    if not await db.market_listings.find_one({"id": lid}, {"_id": 0, "id": 1}):
        raise HTTPException(404, "Listing not found")
    return await db.market_listing_snapshots.find(
        {"market_listing_id": lid}, {"_id": 0},
    ).sort("observed_at", -1).to_list(500)


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


@router.post("/admin/market/listings")
async def ingest_listing(payload: dict, user: dict = Depends(get_current_user)):
    """Ingest a market listing and run the MATCH-1.0 pipeline. The listing is
    upserted by (source_id, source_listing_id), then matched to a master
    property (deterministic → weighted → new master / review case)."""
    for k in ("source_id", "source_listing_id"):
        if not payload.get(k):
            raise HTTPException(400, f"{k} is required")
    return await ingest_market_listing(payload, actor_id=user.get("id"))


@router.post("/admin/market/listings/{lid}/rematch")
async def rerun_match(lid: str, user: dict = Depends(get_current_user)):
    try:
        return await rematch_listing(lid, actor_id=user.get("id"))
    except ValueError as e:
        raise HTTPException(404, str(e))


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
                        for f in ("suburb", "street", "building_name", "allotment_number", "portion_number")]
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
# GUIDANCE ENGINE (GUIDE-1.0)
# ============================================================
@router.post("/admin/market/guidance/run")
async def run_guidance(payload: dict, user: dict = Depends(get_current_user)):
    """Run the guidance engine for a subject property. `payload` must contain
    at minimum: purpose (sale/rent), property_class, suburb. Optional:
    property_subtype, street, local_area, bedrooms, bathrooms, land_area_m2,
    building_area_m2, subject_asking_price, workflow (seller|buyer|landlord|renter|admin)."""
    if payload.get("purpose") not in ("sale", "rent"):
        raise HTTPException(400, "purpose must be 'sale' or 'rent'")
    if not payload.get("suburb"):
        raise HTTPException(400, "suburb is required")
    workflow = payload.pop("workflow", "admin")
    try:
        return await generate_guidance(payload, workflow=workflow,
                                       actor_id=user.get("id"))
    except RuntimeError as e:
        raise HTTPException(400, str(e))


@router.get("/admin/market/guidance/results")
async def list_guidance_results(limit: int = 50, workflow: Optional[str] = None,
                                 user: dict = Depends(get_current_user)):
    q: dict = {}
    if workflow:
        q["outputs.workflow"] = workflow
    return await db.guidance_results.find(q, {"_id": 0}).sort("created_at", -1).to_list(limit)


@router.get("/admin/market/guidance/results/{rid}")
async def get_guidance_result(rid: str, user: dict = Depends(get_current_user)):
    result = await db.guidance_results.find_one({"id": rid}, {"_id": 0})
    if not result:
        raise HTTPException(404, "Guidance result not found")
    comps = await db.guidance_comparables.find(
        {"guidance_result_id": rid}, {"_id": 0},
    ).sort("quality_score", -1).to_list(500)
    req = await db.valuation_requests.find_one({"id": result["valuation_request_id"]}, {"_id": 0})
    return {"result": result, "comparables": comps, "request": req}


# ============================================================
# ANALYTICS (source health strip / trends / heatmap)
# ============================================================
@router.get("/admin/market/analytics/source-strip")
async def analytics_source_strip(days: int = 30, user: dict = Depends(get_current_user)):
    """Compact per-source strip: last N days of run success rate + total
    listings ingested. Powers the Overview health strip."""
    ck = f"source-strip:{days}"
    if (cached := _cache_get(ck)) is not None:
        return cached
    from datetime import datetime, timedelta, timezone
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    sources = await db.market_sources.find({}, {"_id": 0}).to_list(500)
    out = []
    for s in sources:
        runs = await db.collection_runs.find(
            {"source_id": s["id"], "started_at": {"$gte": since}}, {"_id": 0},
        ).to_list(500)
        total = len(runs)
        ok = sum(1 for r in runs if r["status"] == "success")
        listings = sum(int(r.get("listings_new") or 0) for r in runs)
        out.append({
            "source_id": s["id"], "name": s["name"], "active": s.get("active"),
            "collector": s.get("collector"),
            "runs": total,
            "success_rate": round(ok / total * 100, 1) if total else None,
            "listings_ingested": listings,
            "last_run_at": s.get("last_run_at"),
            "consecutive_failures": int(s.get("consecutive_failures") or 0),
        })
    _cache_set(ck, out)
    return out


@router.get("/admin/market/analytics/price-trends")
async def analytics_price_trends(purpose: str = "sale",
                                  months: int = 12,
                                  user: dict = Depends(get_current_user)):
    """Median price per month (all suburbs pooled). Feeds the Overview
    trend line chart."""
    ck = f"price-trends:{purpose}:{months}"
    if (cached := _cache_get(ck)) is not None:
        return cached
    from datetime import datetime, timedelta, timezone
    import statistics
    cutoff = datetime.now(timezone.utc) - timedelta(days=months * 31)
    buckets: dict[str, list[float]] = {}
    async for l in db.market_listings.find(
        {"purpose": purpose, "price": {"$ne": None}, "status": "active"},
        {"_id": 0, "price": 1, "last_seen": 1},
    ):
        try:
            dt = datetime.fromisoformat((l["last_seen"] or "").replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt < cutoff:
                continue
            key = dt.strftime("%Y-%m")
            buckets.setdefault(key, []).append(float(l["price"]))
        except Exception:
            continue
    out = [{"month": k, "count": len(v),
             "median": statistics.median(v) if v else None}
            for k, v in sorted(buckets.items())]
    _cache_set(ck, out)
    return out


@router.get("/admin/market/analytics/median-by-suburb")
async def analytics_median_by_suburb(purpose: str = "sale", limit: int = 12,
                                      user: dict = Depends(get_current_user)):
    ck = f"median-by-suburb:{purpose}:{limit}"
    if (cached := _cache_get(ck)) is not None:
        return cached
    import statistics
    grouped: dict[str, list[float]] = {}
    async for l in db.market_listings.find(
        {"purpose": purpose, "price": {"$ne": None}, "status": "active"},
        {"_id": 0, "price": 1, "suburb": 1},
    ):
        s = (l.get("suburb") or "").strip()
        if not s:
            continue
        grouped.setdefault(s, []).append(float(l["price"]))
    rows = [{"suburb": k, "count": len(v),
             "median": statistics.median(v)}
            for k, v in grouped.items()]
    rows.sort(key=lambda r: r["median"], reverse=True)
    out = rows[:limit]
    _cache_set(ck, out)
    return out


@router.get("/admin/market/analytics/heatmap")
async def analytics_heatmap(purpose: str = "sale", months: int = 12,
                             user: dict = Depends(get_current_user)):
    """Grid of (suburb × month) → median price. Feeds the Trends heatmap."""
    ck = f"heatmap:{purpose}:{months}"
    if (cached := _cache_get(ck)) is not None:
        return cached
    from datetime import datetime, timedelta, timezone
    import statistics
    cutoff = datetime.now(timezone.utc) - timedelta(days=months * 31)
    cells: dict[tuple[str, str], list[float]] = {}
    async for l in db.market_listings.find(
        {"purpose": purpose, "price": {"$ne": None}, "status": "active"},
        {"_id": 0, "price": 1, "suburb": 1, "last_seen": 1},
    ):
        try:
            dt = datetime.fromisoformat((l["last_seen"] or "").replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt < cutoff:
                continue
            suburb = (l.get("suburb") or "").strip() or "—"
            key = (suburb, dt.strftime("%Y-%m"))
            cells.setdefault(key, []).append(float(l["price"]))
        except Exception:
            continue
    months_axis = sorted({k[1] for k in cells.keys()})
    suburbs_axis = sorted({k[0] for k in cells.keys()})
    matrix = []
    for s in suburbs_axis:
        row = {"suburb": s}
        for m in months_axis:
            vals = cells.get((s, m))
            row[m] = statistics.median(vals) if vals else None
        matrix.append(row)
    out = {"months": months_axis, "suburbs": suburbs_axis, "cells": matrix}
    _cache_set(ck, out)
    return out


@router.get("/admin/market/analytics/quick-insights")
async def analytics_quick_insights(user: dict = Depends(get_current_user)):
    """Donut-friendly breakdowns: listings by class, listings by purpose,
    match band distribution."""
    ck = "quick-insights"
    if (cached := _cache_get(ck)) is not None:
        return cached
    async def _agg(collection, field, extra_match=None):
        pipeline = []
        if extra_match:
            pipeline.append({"$match": extra_match})
        pipeline += [
            {"$group": {"_id": f"${field}", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]
        rows = []
        async for doc in collection.aggregate(pipeline):
            rows.append({"key": doc["_id"] or "—", "count": doc["count"]})
        return rows

    out = {
        "by_class": await _agg(db.market_listings, "property_class", {"status": "active"}),
        "by_purpose": await _agg(db.market_listings, "purpose", {"status": "active"}),
        "match_bands": await _agg(db.property_matches, "decision_band", {"status": "active"}),
    }
    _cache_set(ck, out)
    return out


DEFAULT_HEALTH_LED = {"amber_min_success_pct": 90, "red_consecutive_failures": 2}


@router.get("/admin/market/health-led/config")
async def health_led_config(user: dict = Depends(get_current_user)):
    """Thresholds that drive the global Aggregation Health LED badge. Sourced
    from the active MarketConfiguration; falls back to platform defaults."""
    params = await _active_config_params()
    raw = params.get("health_led") or {}
    return {
        "amber_min_success_pct": float(raw.get("amber_min_success_pct",
                                                DEFAULT_HEALTH_LED["amber_min_success_pct"])),
        "red_consecutive_failures": int(raw.get("red_consecutive_failures",
                                                DEFAULT_HEALTH_LED["red_consecutive_failures"])),
    }



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
        "guidance_results": await db.guidance_results.count_documents({}),
        "active_config_version": await _active_config_version(),
    }
