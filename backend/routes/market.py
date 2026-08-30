"""Staff-only Property Data Aggregation and Master Property link endpoints."""
import asyncio
import hashlib
import json
import re
import statistics
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, urlunparse

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


async def _audit(user: dict, action: str, subject_type: str,
                 subject_id: str, payload: dict | None = None) -> None:
    await db.audit_events.insert_one({
        "id": new_id(), "actor_id": user.get("id") or "system", "action": action,
        "subject_type": subject_type, "subject_id": subject_id,
        "payload": payload or {}, "created_at": now_iso(),
    })


def _source_view(row: dict) -> dict:
    item = dict(row)
    item["collector"] = item.get("collector_key")
    item["source_id"] = item.get("id")
    item.setdefault("collection_frequency", "manual")
    item.setdefault("allow_source_auto_match", True)
    item.setdefault("parser_version", "1.0")
    return item


def _normalized_base_url(payload: dict) -> str:
    raw = str(payload.get("base_url") or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(400, "Enter a valid public http or https website address")
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/") or "", "", "", ""))


def _domain(payload: dict) -> str:
    raw = str(payload.get("domain") or "").strip().lower()
    if raw:
        return raw.removeprefix("www.")
    base = _normalized_base_url(payload)
    return (urlparse(base).hostname or "").lower().removeprefix("www.")


def _listing_pages(pages) -> list:
    clean, seen = [], set()
    for page in pages or []:
        url = str((page or {}).get("listing_url") or "").strip()
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or url in seen:
            continue
        seen.add(url)
        clean.append({**page, "listing_url": url})
    return clean


@router.get("/admin/market/sources")
async def list_sources(user: dict = Depends(require_staff)):
    rows = await db.source_sites.find({"archived": {"$ne": True}}, {"_id": 0}).sort("name", 1).to_list(500)
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
        "base_url": _normalized_base_url(payload),
        "description": payload.get("description"), "active": bool(payload.get("active", True)),
        "is_trel_owned": bool(payload.get("is_trel_owned", False)),
        "collector_key": payload.get("collector") or payload.get("collector_key") or "generic_web",
        "collection_frequency": payload.get("collection_frequency") or "manual",
        "allow_source_auto_match": bool(payload.get("allow_source_auto_match", True)),
        "parser_version": payload.get("parser_version") or "1.0",
        "listing_pages": _listing_pages(payload.get("listing_pages")),
        "parser_config": payload.get("parser_config") or {},
        "created_at": timestamp, "updated_at": timestamp,
    }
    await db.source_sites.insert_one(document)
    document.pop("_id", None)
    await _audit(user, "MARKET_SOURCE_CREATED", "market_source", document["id"], {"name": document["name"], "domain": domain})
    return _source_view(document)


@router.put("/admin/market/sources/{source_site_id}")
async def update_source(source_site_id: str, payload: dict, user: dict = Depends(require_staff)):
    existing = await db.source_sites.find_one({"id": source_site_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Source not found")
    patch = dict(payload)
    if "base_url" in patch:
        patch["base_url"] = _normalized_base_url(patch)
    if "listing_pages" in patch:
        patch["listing_pages"] = _listing_pages(patch["listing_pages"])
    if "collector" in patch:
        patch["collector_key"] = patch.pop("collector")
    patch["domain"] = _domain({**existing, **patch})
    patch["updated_at"] = now_iso()
    patch.pop("id", None)
    await db.source_sites.update_one({"id": source_site_id}, {"$set": patch})
    await _audit(user, "MARKET_SOURCE_UPDATED", "market_source", source_site_id, {"changed_fields": sorted(patch)})
    return _source_view({**existing, **patch})


@router.delete("/admin/market/sources/{source_site_id}")
async def delete_source(source_site_id: str, user: dict = Depends(require_staff)):
    source = await db.source_sites.find_one({"id": source_site_id}, {"_id": 0})
    if not source:
        raise HTTPException(404, "Source not found")
    await db.source_sites.update_one({"id": source_site_id}, {"$set": {
        "archived": True, "active": False, "archived_at": now_iso(),
        "archived_by": user["id"], "updated_at": now_iso(),
    }, "$unset": {"collection_lock": "", "collection_lock_at": ""}})
    await db.audit_events.insert_one({
        "id": new_id(), "subject_type": "market_source", "subject_id": source_site_id,
        "action": "SOURCE_DELETED_LISTINGS_RETAINED", "actor_id": user["id"],
        "payload": {"name": (source or {}).get("name")}, "created_at": now_iso(),
    })
    return {"ok": True, "listings_retained": True}


@router.post("/admin/market/listings")
async def ingest_market_listing(payload: MarketObservationCreate, user: dict = Depends(require_staff)):
    try:
        return await service.ingest(payload.model_dump(), user["id"])
    except ValueError as exc:
        raise HTTPException(400, str(exc))


_ACTIVE_COLLECTION_TASKS: dict[str, asyncio.Task] = {}
_STALE_RUN_MINUTES = 10


class CollectionRunContext:
    """In-memory diagnostics mirrored to the collection run document."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.cancel_requested = False
        self._page_cards_total = 0
        self.diagnostics = {
            "pages_visited": [], "pages_visited_total": 0, "pages_truncated": False,
            "cards_seen": 0, "cards_accepted": 0,
            "cards_rejected": 0, "cards_unpriced": 0, "rejection_reasons": {},
            "duplicate_source_ids_within_run": 0, "pagination_pages_followed": 0,
            "detail_pages_attempted": 0, "detail_pages_succeeded": 0,
            "detail_pages_failed": 0, "records_passed_to_ingestion": 0,
            "records_inserted": 0, "records_updated": 0,
            "pagination_end_reason": None,
            "phase": "STARTING", "current_url": None, "current_status": None,
        }

    def record_diag(self, reason: str, *, inc: str | None = None,
                    url: str | None = None, status: int | None = None) -> None:
        phase_by_reason = {
            "page_fetch_started": "FETCHING_LIST_PAGE",
            "page_fetched": "PARSING_LIST_PAGE",
            "detail_page_attempted": "FETCHING_DETAIL_PAGE",
            "card_accepted": "PROCESSING_LISTINGS",
            "page_fetch_failed": "LIST_PAGE_FAILED",
        }
        if reason in phase_by_reason:
            self.diagnostics["phase"] = phase_by_reason[reason]
        if url:
            self.diagnostics["current_url"] = url
        if status is not None:
            self.diagnostics["current_status"] = status
        if reason == "card_seen":
            self.diagnostics["cards_seen"] += 1
        elif reason in {"card_accepted"}:
            self.diagnostics["cards_accepted"] += 1
        elif reason in {"no_url_in_card", "no_numeric_price", "unpriced_listing", "duplicate_source_id_within_run"}:
            self.diagnostics["cards_rejected"] += 1
            if reason == "unpriced_listing":
                self.diagnostics["cards_unpriced"] += 1
            reasons = self.diagnostics["rejection_reasons"]
            reasons[reason] = reasons.get(reason, 0) + 1
        if reason == "duplicate_source_id_within_run":
            self.diagnostics["duplicate_source_ids_within_run"] += 1
        if inc:
            self.diagnostics[inc] = self.diagnostics.get(inc, 0) + 1
        if reason == "page_fetch_failed":
            self.diagnostics.setdefault("errors", []).append(
                {"url": url, "status": status, "reason": reason}
            )

    def record_page(self, url: str, cards_seen: int, cards_accepted: int,
                    cards_rejected: int, final: bool = False) -> None:
        self.diagnostics["pages_visited_total"] += 1
        if len(self.diagnostics["pages_visited"]) < 200:
            self.diagnostics["pages_visited"].append({
                "url": url, "cards_seen": cards_seen,
                "cards_accepted": cards_accepted, "cards_rejected": cards_rejected,
                "final": final,
            })
        else:
            self.diagnostics["pages_truncated"] = True
        self._page_cards_total += cards_seen
        self.diagnostics["cards_seen"] = max(self.diagnostics["cards_seen"], self._page_cards_total)
        self.diagnostics["pagination_pages_followed"] = self.diagnostics["pages_visited_total"]
        self.diagnostics["phase"] = "PAGE_COMPLETE"
        self.diagnostics["current_url"] = url

    def record_pagination_end(self, reason: str) -> None:
        self.diagnostics["pagination_end_reason"] = reason
        self.diagnostics["phase"] = "PAGINATION_COMPLETE"

    def request_cancel(self) -> None:
        self.cancel_requested = True

    def raise_if_cancelled(self) -> None:
        if self.cancel_requested:
            raise asyncio.CancelledError()


async def _mark_stale_runs() -> None:
    """Close abandoned runs without allowing malformed legacy rows to cause 500s."""
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=_STALE_RUN_MINUTES)).isoformat()
    rows = await db.collection_runs.find({
        "status": "RUNNING",
        "$or": [{"heartbeat_at": {"$lt": cutoff}}, {
            "heartbeat_at": {"$exists": False}, "started_at": {"$lt": cutoff}
        }],
    }, {"_id": 0}).to_list(500)
    for row in rows:
        task = _ACTIVE_COLLECTION_TASKS.get(row.get("id"))
        if task and not task.done():
            continue
        patch = {
            "status": "FAILED", "outcome": "STALE", "finished_at": now_iso(),
            "error": "Run heartbeat expired; it can be safely retried.",
        }
        try:
            await db.collection_runs.update_one({"id": row["id"]}, {"$set": patch})
        except Exception:
            # Pre-lifecycle test rows can violate the current strict validator.
            # They contain no usable results, so remove only that malformed run.
            await db.collection_runs.delete_one({"id": row["id"]})
        await db.source_sites.update_one(
            {"id": row.get("source_site_id"), "collection_lock": row.get("id")},
            {"$unset": {"collection_lock": "", "collection_lock_at": ""}},
        )


async def resume_pending_collection_runs() -> None:
    """Recover aggregation work after a Fly restart without another queue."""
    await _mark_stale_runs()
    rows = await db.collection_runs.find({"status": "RUNNING"}, {"_id": 0}).to_list(100)
    for run in rows:
        if run.get("cancel_requested") or _run_heartbeat_expired(run):
            continue
        source = await db.source_sites.find_one({"id": run.get("source_site_id"), "active": True}, {"_id": 0})
        if not source or run["id"] in _ACTIVE_COLLECTION_TASKS:
            continue
        run.setdefault("records_validation_rejected", 0)
        run.setdefault("created_by", "system")
        task = asyncio.create_task(_execute_collection_run(run, source, run["created_by"]))
        _ACTIVE_COLLECTION_TASKS[run["id"]] = task
        task.add_done_callback(lambda _task, rid=run["id"]: _ACTIVE_COLLECTION_TASKS.pop(rid, None))


async def ensure_market_indexes() -> None:
    """Install only aggregation invariants and repair duplicate legacy locks."""
    await _mark_stale_runs()
    active = await db.collection_runs.find({"status": "RUNNING"}, {"_id": 0}).sort("started_at", -1).to_list(500)
    newest_by_source = {}
    for run in active:
        source_id = run.get("source_site_id")
        if source_id not in newest_by_source:
            newest_by_source[source_id] = run["id"]
            continue
        await db.collection_runs.update_one({"id": run["id"]}, {"$set": {
            "status": "FAILED", "outcome": "STALE", "finished_at": now_iso(),
            "error": "Duplicate legacy run was closed during aggregation startup.",
        }})
    duplicate_groups = await db.source_listings.aggregate([
        {"$group": {"_id": {"source": "$source_site_id", "listing": "$source_listing_id"},
                    "ids": {"$push": "$id"}, "count": {"$sum": 1}}},
        {"$match": {"count": {"$gt": 1}}},
    ]).to_list(1000)
    for group in duplicate_groups:
        rows = await db.source_listings.find({"id": {"$in": group["ids"]}}, {"_id": 0}).sort("updated_at", -1).to_list(len(group["ids"]))
        if len(rows) < 2:
            continue
        keeper, duplicate_ids = rows[0], [row["id"] for row in rows[1:]]
        await db.source_listing_observations.update_many(
            {"source_listing_id": {"$in": duplicate_ids}}, {"$set": {"source_listing_id": keeper["id"]}}
        )
        await db.property_match_reviews.update_many(
            {"source_listing_id": {"$in": duplicate_ids}}, {"$set": {"source_listing_id": keeper["id"], "updated_at": now_iso()}}
        )
        await db.source_listings.delete_many({"id": {"$in": duplicate_ids}})
    await db.collection_runs.create_index(
        [("source_site_id", 1), ("status", 1)], unique=True,
        partialFilterExpression={"status": "RUNNING"}, name="one_running_collection_per_source",
    )
    await db.source_listings.create_index(
        [("source_site_id", 1), ("source_listing_id", 1)], unique=True,
        name="one_listing_identity_per_source",
    )
    await db.source_listing_observations.create_index(
        [("source_listing_id", 1), ("observed_at", -1)],
        name="listing_observation_history",
    )


def _run_heartbeat_expired(run: dict, current_time: datetime | None = None) -> bool:
    heartbeat = run.get("heartbeat_at") or run.get("started_at")
    try:
        stamp = datetime.fromisoformat(str(heartbeat).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        return stamp < (current_time or datetime.now(timezone.utc)) - timedelta(minutes=_STALE_RUN_MINUTES)
    except (TypeError, ValueError):
        return True


async def _clear_orphaned_source_lock(source_site_id: str) -> None:
    """Release a source lock when its run is missing, finished, or expired."""
    source = await db.source_sites.find_one(
        {"id": source_site_id}, {"_id": 0, "collection_lock": 1}
    )
    lock_id = (source or {}).get("collection_lock")
    if not lock_id:
        return
    run = await db.collection_runs.find_one({"id": lock_id}, {"_id": 0})
    release = not run or str(run.get("status") or "").upper() != "RUNNING"
    if run and not release:
        release = _run_heartbeat_expired(run)
    if not release:
        return
    if run and str(run.get("status") or "").upper() == "RUNNING":
        try:
            await db.collection_runs.update_one({"id": lock_id}, {"$set": {
                "status": "FAILED", "outcome": "STALE", "finished_at": now_iso(),
                "error": "Orphaned source lock was automatically recovered.",
            }})
        except Exception:
            await db.collection_runs.delete_one({"id": lock_id})
    await db.source_sites.update_one(
        {"id": source_site_id, "collection_lock": lock_id},
        {"$unset": {"collection_lock": "", "collection_lock_at": ""}},
    )


async def _persist_progress(run: dict, context: CollectionRunContext) -> None:
    context.raise_if_cancelled()
    control = await db.collection_runs.find_one(
        {"id": run["id"]}, {"_id": 0, "cancel_requested": 1}
    )
    if control and control.get("cancel_requested"):
        context.request_cancel()
        context.raise_if_cancelled()
    run["records_seen"] = context.diagnostics.get("cards_seen", 0)
    run["records_accepted"] = context.diagnostics.get("cards_accepted", 0)
    run["records_rejected"] = context.diagnostics.get("cards_rejected", 0) + run.get("records_validation_rejected", 0)
    context.diagnostics["records_passed_to_ingestion"] = run["records_ingested"]
    context.diagnostics["records_inserted"] = run["records_new"]
    context.diagnostics["records_updated"] = run["records_updated"]
    await db.collection_runs.update_one({"id": run["id"]}, {"$set": {
        "heartbeat_at": now_iso(), "records_seen": run["records_seen"],
        "records_ingested": run["records_ingested"],
        "records_new": run["records_new"], "records_updated": run["records_updated"],
        "records_rejected": run["records_rejected"],
        "records_matched": run["records_matched"],
        "records_review_required": run["records_review_required"],
        "diagnostics": context.diagnostics,
    }})


async def _progress_heartbeat(run: dict, context: CollectionRunContext) -> None:
    """Persist live diagnostics while the collector is waiting on network I/O."""
    while True:
        await _persist_progress(run, context)
        await asyncio.sleep(2)


async def _execute_collection_run(run: dict, source: dict, actor_id: str) -> None:
    context = CollectionRunContext(run["id"])
    heartbeat = asyncio.create_task(_progress_heartbeat(run, context))
    try:
        collector_class = get_collector(source.get("collector_key") or "")
        collector = collector_class(source)
        async for row in collector.iter_listings(run=context):
            context.raise_if_cancelled()
            normalized = collector_payload(source["id"], row)
            if not normalized["source_listing_id"] or not normalized["source_url"]:
                run["records_validation_rejected"] = run.get("records_validation_rejected", 0) + 1
                await _persist_progress(run, context)
                continue
            existed = await db.source_listings.find_one({
                "source_site_id": source["id"],
                "source_listing_id": normalized["source_listing_id"],
            }, {"_id": 0, "id": 1})
            result = await service.ingest(normalized, actor_id)
            run["records_ingested"] += 1
            run["records_updated" if existed else "records_new"] += 1
            if result["match"]["status"] == "MATCHED":
                run["records_matched"] += 1
            elif result["match"]["status"] == "REVIEW_REQUIRED":
                run["records_review_required"] += 1
            await _persist_progress(run, context)
        run["records_seen"] = context.diagnostics.get("cards_seen", 0)
        run["records_accepted"] = context.diagnostics.get("cards_accepted", 0)
        run["records_rejected"] = context.diagnostics.get("cards_rejected", 0) + run.get("records_validation_rejected", 0)
        reasons = context.diagnostics.get("rejection_reasons") or {}
        extraction_failures = int(reasons.get("no_url_in_card", 0)) + int(reasons.get("no_numeric_price", 0))
        cards_seen = int(context.diagnostics.get("cards_seen") or 0)
        pages_seen = int(context.diagnostics.get("pages_visited_total") or 0)
        context.diagnostics["drift_detected"] = bool(
            run["records_ingested"] == 0 and pages_seen > 0 and (
                cards_seen == 0 or extraction_failures >= max(1, int(cards_seen * 0.8))
            )
        )
        outcome = "NO_DATA" if run["records_ingested"] == 0 else (
            "WARNING" if run["records_rejected"] or context.diagnostics.get("errors") else "COMPLETED"
        )
        run.update(status="SUCCESS", outcome=outcome, finished_at=now_iso(), error=None)
        context.diagnostics["phase"] = "COMPLETED"
    except asyncio.CancelledError:
        context.request_cancel()
        run.update(
            status="FAILED", outcome="CANCELLED", finished_at=now_iso(),
            error="Cancelled by staff; all collection work for this run was stopped.",
        )
        context.diagnostics["phase"] = "CANCELLED"
    except Exception as exc:
        run.update(status="FAILED", outcome="FAILED", finished_at=now_iso(), error=str(exc)[:1000])
        context.diagnostics["phase"] = "FAILED"
    finally:
        heartbeat.cancel()
        with suppress(asyncio.CancelledError, Exception):
            await heartbeat
        run["records_seen"] = context.diagnostics.get("cards_seen", 0)
        run["records_accepted"] = context.diagnostics.get("cards_accepted", 0)
        run["records_rejected"] = context.diagnostics.get("cards_rejected", 0) + run.get("records_validation_rejected", 0)
        context.diagnostics["records_passed_to_ingestion"] = run["records_ingested"]
        context.diagnostics["records_inserted"] = run["records_new"]
        context.diagnostics["records_updated"] = run["records_updated"]
        await db.collection_runs.update_one({"id": run["id"]}, {"$set": {
            **run, "diagnostics": context.diagnostics, "heartbeat_at": now_iso(),
        }})
        profile_status = "DRIFTED" if context.diagnostics.get("drift_detected") else (
            "HEALTHY" if run.get("records_ingested", 0) > 0 else "NO_DATA"
        )
        await db.source_sites.update_one(
            {"id": source["id"], "collection_lock": run["id"]},
            {"$set": {"last_run_at": run["finished_at"], "updated_at": now_iso(),
                      "profile_status": profile_status},
             "$unset": {"collection_lock": "", "collection_lock_at": ""}},
        )


@router.post("/admin/market/sources/{source_site_id}/collect", status_code=202)
async def collect_source(source_site_id: str, user: dict = Depends(require_staff)):
    await _mark_stale_runs()
    await _clear_orphaned_source_lock(source_site_id)
    source = await db.source_sites.find_one({"id": source_site_id}, {"_id": 0})
    if not source or not source.get("active", True):
        raise HTTPException(404, "Active source site not found")
    if not get_collector(source.get("collector_key") or ""):
        raise HTTPException(400, "Source site has no supported collector")
    active = await db.collection_runs.find_one(
        {"source_site_id": source_site_id, "status": "RUNNING"}, {"_id": 0}
    )
    if active:
        item = _run_view(active)
        item["already_running"] = True
        return item
    run_id = new_id()
    locked = await db.source_sites.find_one_and_update(
        {"id": source_site_id, "$or": [
            {"collection_lock": {"$exists": False}}, {"collection_lock": None},
        ]},
        {"$set": {"collection_lock": run_id, "collection_lock_at": now_iso()}},
    )
    if not locked:
        active = await db.collection_runs.find_one(
            {"source_site_id": source_site_id, "status": "RUNNING"}, {"_id": 0}
        )
        if active:
            item = _run_view(active)
            item["already_running"] = True
            return item
        raise HTTPException(503, "The source lock could not be recovered; refresh and retry")
    run = {
        "id": run_id, "source_site_id": source_site_id,
        "source_name": source.get("name"), "source_domain": source.get("domain"),
        "status": "RUNNING", "outcome": "RUNNING", "started_at": now_iso(),
        "heartbeat_at": now_iso(), "finished_at": None, "cancel_requested": False,
        "records_seen": 0, "records_accepted": 0, "records_ingested": 0, "records_new": 0,
        "records_updated": 0, "records_rejected": 0, "records_validation_rejected": 0, "records_matched": 0,
        "records_review_required": 0, "created_by": user["id"], "errors": [],
    }
    try:
        await db.collection_runs.insert_one(run)
    except Exception:
        await db.source_sites.update_one(
            {"id": source_site_id, "collection_lock": run_id},
            {"$unset": {"collection_lock": "", "collection_lock_at": ""}},
        )
        raise HTTPException(503, "Collection run could not be created; retry after the run records are repaired")
    run.pop("_id", None)
    task = asyncio.create_task(_execute_collection_run(run, source, user["id"]))
    _ACTIVE_COLLECTION_TASKS[run_id] = task
    task.add_done_callback(lambda _task, rid=run_id: _ACTIVE_COLLECTION_TASKS.pop(rid, None))
    await _audit(user, "COLLECTION_RUN_STARTED", "collection_run", run_id, {"source_site_id": source_site_id, "source_name": source.get("name")})
    return _run_view(run)


@router.post("/admin/market/runs/{run_id}/cancel", status_code=202)
async def cancel_collection_run(run_id: str, user: dict = Depends(require_staff)):
    run = await db.collection_runs.find_one({"id": run_id}, {"_id": 0})
    if not run:
        raise HTTPException(404, "Collection run not found")
    if run.get("status") != "RUNNING":
        raise HTTPException(409, "Only a running collection can be cancelled")
    await db.collection_runs.update_one({"id": run_id}, {"$set": {
        "cancel_requested": True, "outcome": "CANCELLING", "cancel_requested_at": now_iso(),
        "cancel_requested_by": user["id"],
    }})
    task = _ACTIVE_COLLECTION_TASKS.get(run_id)
    if task and not task.done():
        task.cancel()
    else:
        await db.collection_runs.update_one({"id": run_id}, {"$set": {
            "status": "FAILED", "outcome": "CANCELLED", "finished_at": now_iso(),
            "error": "Cancelled by staff after the worker stopped responding.",
        }})
        await db.source_sites.update_one(
            {"id": run.get("source_site_id"), "collection_lock": run_id},
            {"$unset": {"collection_lock": "", "collection_lock_at": ""}},
        )
    await _audit(user, "COLLECTION_RUN_CANCEL_REQUESTED", "collection_run", run_id, {"source_site_id": run.get("source_site_id")})
    return {"ok": True, "run_id": run_id, "status": "cancelling"}


def _run_view(row: dict) -> dict:
    item = dict(row)
    item["source_id"] = item.get("source_site_id")
    item["listings_seen"] = item.get("records_seen", 0)
    item["listings_new"] = item.get("records_new", item.get("records_ingested", 0))
    item["listings_updated"] = item.get("records_updated", 0)
    item["listings_rejected"] = item.get("records_rejected", 0)
    item["matches_created"] = item.get("records_matched", 0)
    item["review_cases_created"] = item.get("records_review_required", 0)
    item.setdefault("diagnostics", {
        "phase": str(item.get("outcome") or item.get("status") or "UNKNOWN").upper(),
        "pages_visited": [], "pages_visited_total": 0, "cards_seen": item.get("records_seen", 0),
        "cards_accepted": item.get("records_ingested", 0), "cards_rejected": item.get("records_rejected", 0),
        "rejection_reasons": {}, "pagination_end_reason": "legacy_run_no_page_diagnostics",
    })
    outcome = str(item.get("outcome") or "").lower()
    item["status"] = outcome if outcome in {
        "no_data", "warning", "cancelled", "cancelling", "stale"
    } else str(item.get("status") or "").lower()
    return item


@router.get("/admin/market/runs")
async def list_runs(source_id: str = None, limit: int = 100, user: dict = Depends(require_staff)):
    try:
        await _mark_stale_runs()
    except Exception:
        # Run history must remain readable even if one legacy row is malformed.
        pass
    query = {"source_site_id": source_id} if source_id else {}
    rows = await db.collection_runs.find(query, {"_id": 0}).sort("started_at", -1).limit(limit).to_list(limit)
    missing_ids = {r.get("source_site_id") for r in rows if not r.get("source_name")}
    source_rows = await db.source_sites.find(
        {"id": {"$in": list(missing_ids)}}, {"_id": 0, "id": 1, "name": 1, "domain": 1}
    ).to_list(len(missing_ids)) if missing_ids else []
    names = {r["id"]: r for r in source_rows}
    for row in rows:
        source_row = names.get(row.get("source_site_id"), {})
        row.setdefault("source_name", source_row.get("name"))
        row.setdefault("source_domain", source_row.get("domain"))
    return [_run_view(row) for row in rows]


@router.get("/admin/market/sources/health")
async def source_health(user: dict = Depends(require_staff)):
    sources = await db.source_sites.find({"archived": {"$ne": True}}, {"_id": 0}).to_list(500)
    result = []
    for source in sources:
        runs = await db.collection_runs.find({"source_site_id": source["id"]}, {"_id": 0}).sort("started_at", -1).limit(10).to_list(10)
        useful = lambda run: str(run.get("outcome") or "").upper() in {"COMPLETED", "WARNING"} and int(run.get("records_ingested") or 0) > 0
        completed = [run for run in runs if str(run.get("status") or "").upper() != "RUNNING"]
        successes = sum(1 for run in completed if useful(run))
        result.append({
            "source_id": source["id"], "name": source.get("name") or source.get("domain"),
            "domain": source.get("domain"), "collector": source.get("collector_key"),
            "runs": len(runs), "success_rate": round(successes * 100 / len(completed), 1) if completed else None,
            "consecutive_failures": next((index for index, run in enumerate(completed) if useful(run)), len(completed)),
            "listings_ingested": await db.source_listings.count_documents({"source_site_id": source["id"]}),
            "profile_status": source.get("profile_status"), "last_run_at": source.get("last_run_at"),
        })
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
    base_url = _normalized_base_url(payload)
    cache_key = hashlib.sha256(json.dumps({
        "url": base_url, "collector": key, "parser": payload.get("parser_config") or {},
    }, sort_keys=True).encode()).hexdigest()
    cache_id = f"market_discovery:{cache_key}"
    cached = await db.system_settings.find_one({"id": cache_id}, {"_id": 0})
    if cached and not payload.get("force"):
        try:
            created = datetime.fromisoformat(str(cached.get("created_at") or "").replace("Z", "+00:00"))
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if created > datetime.now(timezone.utc) - timedelta(hours=24):
                return {**(cached.get("result") or {}), "cache_hit": True}
        except (TypeError, ValueError):
            pass
    result = await discover_listing_pages(base_url, key, payload.get("parser_config"))
    await db.system_settings.update_one({"id": cache_id}, {"$set": {
        "id": cache_id, "kind": "market_discovery_cache", "created_at": now_iso(),
        "result": result,
    }}, upsert=True)
    return {**result, "cache_hit": False}


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
        before = _listing_pages(source.get("listing_pages"))
        if not source.get("base_url") or not source.get("collector"):
            diffs.append({"source_id": source["id"], "source_name": source["name"], "base_url": source.get("base_url"),
                          "ok": False, "skipped": True, "error": "Source has no website or collector",
                          "before": before, "existing": before, "suggested": [], "added": [], "removed": [], "unchanged": []})
            continue
        try:
            discovered = await discover_listing_pages(source["base_url"], source["collector"], source.get("parser_config"))
            suggested = _listing_pages(discovered.get("candidates"))
            old_urls = {p.get("listing_url") for p in before}
            new_urls = {p.get("listing_url") for p in suggested}
            diffs.append({"source_id": source["id"], "source_name": source["name"], "base_url": source.get("base_url"),
                          "ok": True, "skipped": False, "error": None, "before": before, "existing": before,
                          "suggested": suggested, "added": sorted(new_urls - old_urls),
                          "removed": sorted(old_urls - new_urls), "unchanged": sorted(old_urls & new_urls),
                          "changed": old_urls != new_urls})
        except Exception as exc:
            diffs.append({"source_id": source["id"], "source_name": source["name"], "base_url": source.get("base_url"),
                          "ok": False, "skipped": False, "error": str(exc)[:500], "before": before,
                          "existing": before, "suggested": [], "added": [], "removed": [], "unchanged": []})
    return {
        "total": len(rows), "diffs": diffs,
        "with_changes": sum(1 for d in diffs if d.get("ok") and (d["added"] or d["removed"])),
        "errors": sum(1 for d in diffs if not d.get("ok") and not d.get("skipped")),
        "unchanged": sum(1 for d in diffs if d.get("ok") and not d["added"] and not d["removed"]),
        "skipped": sum(1 for d in diffs if d.get("skipped")),
    }


@router.put("/admin/market/sources/{source_site_id}/listing-pages")
async def save_listing_pages(source_site_id: str, payload: dict, user: dict = Depends(require_staff)):
    pages = _listing_pages(payload.get("listing_pages") or payload.get("pages"))
    result = await db.source_sites.update_one({"id": source_site_id}, {"$set": {"listing_pages": pages, "updated_at": now_iso()}})
    if not result.matched_count:
        raise HTTPException(404, "Source not found")
    return {"ok": True, "listing_pages": pages}


@router.get("/admin/market/master-properties")
async def list_master_properties(search: str = "", limit: int = Query(default=100, ge=1, le=500),
                                 offset: int = Query(default=0, ge=0), user: dict = Depends(require_staff)):
    query = {"lifecycle_status": {"$ne": "deleted"}}
    if search.strip():
        term = search.strip()
        query["$or"] = [
            {"id": {"$regex": term, "$options": "i"}},
            {"canonical_address": {"$regex": term, "$options": "i"}},
            {"property_type": {"$regex": term, "$options": "i"}},
        ]
    rows = await db.master_properties.find(query, {"_id": 0}).sort("updated_at", -1).skip(offset).limit(limit).to_list(limit)
    for row in rows:
        row["source_listing_count"] = await db.source_listings.count_documents({"master_property_id": row.get("id")})
        address = await db.property_addresses.find_one(
            {"property_id": row.get("id"), "is_canonical": True}, {"_id": 0}
        ) or {}
        parcel = await db.property_parcels.find_one({"property_id": row.get("id")}, {"_id": 0}) or {}
        row.setdefault("canonical_address", address.get("formatted_address") or address.get("canonical_address"))
        row["location"] = {key: address.get(key) for key in (
            "street_name", "suburb_name", "local_area_name", "city_name", "province_name"
        ) if address.get(key)}
        row["parcel"] = {key: parcel.get(key) for key in (
            "lot", "section", "portion", "lot_norm", "section_norm", "portion_norm"
        ) if parcel.get(key)}
        row["linked"] = row["source_listing_count"] > 0
    return rows


@router.get("/admin/market/listings")
async def list_market_listings(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    source_id: str | None = None,
    status: str | None = None,
    search: str | None = None,
    user: dict = Depends(require_staff),
):
    return await service.list_evidence(limit, skip=offset, source_id=source_id, status=status, search=search)


@router.get("/admin/market/summary")
async def market_summary(user: dict = Depends(require_staff)):
    summary = await service.summary()
    summary.update({
        "sources": await db.source_sites.count_documents({"archived": {"$ne": True}}),
        "active_sources": await db.source_sites.count_documents({"active": True, "archived": {"$ne": True}}),
        "market_listings": await db.source_listings.count_documents({}),
        "active_listings": await db.source_listings.count_documents({"current_status": "ACTIVE"}),
        "matches_active": await db.source_listings.count_documents({"match_status": "MATCHED"}),
        "review_cases_open": await db.property_match_reviews.count_documents({"status": "OPEN"}),
        "audit_events": await db.audit_events.count_documents({"subject_type": {"$in": [
            "source_listing", "market_source", "collection_run", "master_property",
            "property_match", "market_review_case", "market_configuration",
        ]}}),
    })
    active = await db.system_settings.find_one({"kind": "market_configuration", "active": True}, {"_id": 0, "version": 1, "name": 1})
    summary["active_config_version"] = (active or {}).get("version") or (active or {}).get("name") or "Not configured"
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
async def list_review_cases(status: str = "open", case_type: str = None, limit: int = 100,
                            offset: int = Query(default=0, ge=0), user: dict = Depends(require_staff)):
    query = {"status": status.upper()}
    if case_type:
        query["$or"] = [{"case_type": case_type}, {"case_type": {"$exists": False}}]
    rows = await db.property_match_reviews.find(query, {"_id": 0}).sort("created_at", -1).skip(offset).limit(limit).to_list(limit)
    return [{**row, "status": str(row.get("status") or "").lower(), "case_type": row.get("case_type") or "possible"} for row in rows]


@router.put("/admin/market/review-cases/{review_id}")
async def update_review_case(review_id: str, payload: dict, user: dict = Depends(require_staff)):
    patch = {**payload, "status": str(payload.get("status") or "open").upper(), "updated_at": now_iso()}
    result = await db.property_match_reviews.update_one({"id": review_id}, {"$set": patch})
    if not result.matched_count:
        raise HTTPException(404, "Review case not found")
    await _audit(user, "MARKET_REVIEW_UPDATED", "market_review_case", review_id, {"status": patch["status"]})
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
    await _audit(user, "PROPERTY_MATCH_REVIEW_RESOLVED", "property_match", review_id, {"decision": decision, "master_property_id": master_property_id})
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
        suburb = re.sub(r"\s+", " ", str(row.get("suburb_name") or row.get("local_area_name") or row.get("city_name") or "").strip()).title()
        if suburb:
            grouped.setdefault(suburb, []).append(float(price["amount"]))
    result = [{"suburb": key, "count": len(values), "median": statistics.median(values)} for key, values in grouped.items()]
    return sorted(result, key=lambda item: item["median"], reverse=True)[:limit]


@router.get("/admin/market/analytics/heatmap")
async def heatmap(purpose: str = "sale", months: int = 12, user: dict = Depends(require_staff)):
    cutoff = datetime.now(timezone.utc) - timedelta(days=months * 31)
    grouped = {}
    month_keys = set()
    for row, price in await _priced_rows(purpose):
        try:
            observed = datetime.fromisoformat(str(row.get("observed_at") or "").replace("Z", "+00:00"))
            if observed.tzinfo is None:
                observed = observed.replace(tzinfo=timezone.utc)
            if observed < cutoff:
                continue
        except Exception:
            continue
        suburb = re.sub(r"\s+", " ", str(row.get("suburb_name") or row.get("local_area_name") or row.get("city_name") or "Unknown").strip()).title()
        month = observed.strftime("%Y-%m")
        grouped.setdefault(suburb, {}).setdefault(month, []).append(float(price["amount"]))
        month_keys.add(month)
    months_out = sorted(month_keys)
    cells = [{"suburb": suburb, **{month: statistics.median(values) for month, values in buckets.items()}}
             for suburb, buckets in grouped.items()]
    cells.sort(key=lambda item: item["suburb"])
    return {"months": months_out, "suburbs": [row["suburb"] for row in cells], "cells": cells}


@router.get("/admin/market/analytics/source-strip")
async def source_strip(user: dict = Depends(require_staff)):
    return await source_health(user)


@router.get("/admin/market/analytics/quick-insights")
async def quick_insights(user: dict = Depends(require_staff)):
    rows = await db.source_listings.find({}, {"_id": 0, "id": 1, "transaction_type": 1, "match_status": 1}).to_list(10000)
    ids = [row["id"] for row in rows]
    observations = await db.source_listing_observations.find(
        {"source_listing_id": {"$in": ids}}, {"_id": 0, "source_listing_id": 1, "property_type_name": 1}
    ).to_list(10000) if ids else []
    latest_class = {}
    for item in observations:
        latest_class.setdefault(item["source_listing_id"], item.get("property_type_name") or "Unknown")
    def counts(values):
        output = {}
        for value in values:
            key = str(value or "Unknown").title()
            output[key] = output.get(key, 0) + 1
        return [{"key": key, "count": count} for key, count in sorted(output.items())]
    return {
        "by_class": counts(latest_class.get(row["id"]) for row in rows),
        "by_purpose": counts(row.get("transaction_type") for row in rows),
        "match_bands": counts(row.get("match_status") for row in rows),
    }


@router.post("/admin/market/guidance/run")
async def run_guidance(payload: dict, user: dict = Depends(require_staff)):
    if not str(payload.get("property_subtype") or payload.get("property_class") or "").strip():
        raise HTTPException(400, "Property subtype is required")
    if not str(payload.get("suburb") or payload.get("city") or "").strip():
        raise HTTPException(400, "Suburb or city is required")
    request_payload = {
        "property_id": payload.get("property_id"), "property_type": payload.get("property_subtype") or payload.get("property_class") or "House",
        "listing_type": payload.get("purpose") or "sale", "price": float(payload.get("subject_asking_price") or 1),
        "province": payload.get("province"), "city": payload.get("city") or payload.get("suburb"),
        "suburb": payload.get("suburb"), "local_area": payload.get("local_area"),
        "bedrooms": payload.get("bedrooms"), "bathrooms": payload.get("bathrooms"),
        "land_area_sqm": payload.get("land_area_m2"), "building_area_sqm": payload.get("building_area_m2"),
    }
    result = await price_guidance.analyse(request_payload)
    wrapper = {
        "id": new_id(), "created_at": now_iso(),
        "outputs": {"workflow": payload.get("workflow") or "admin"},
        "subject": request_payload, "comparable_count": result.get("sample_size", 0),
        "confidence_label": result.get("evidence_strength"),
        "range": {"low": result.get("range_min"), "high": result.get("range_max")},
        **result,
    }
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
async def audit_events(entity_type: str = None, event_type: str = None, limit: int = 100,
                       offset: int = Query(default=0, ge=0), user: dict = Depends(require_staff)):
    query = {}
    if entity_type:
        query["subject_type"] = entity_type
    if event_type:
        query["action"] = event_type
    rows = await db.audit_events.find(query, {"_id": 0}).sort("created_at", -1).skip(offset).limit(limit).to_list(limit)
    return [{**row, "event_type": row.get("event_type") or row.get("action"),
             "entity_type": row.get("entity_type") or row.get("subject_type"),
             "entity_id": row.get("entity_id") or row.get("subject_id")} for row in rows]


@router.get("/admin/market/config")
async def list_config(user: dict = Depends(require_staff)):
    return await db.system_settings.find({"kind": "market_configuration"}, {"_id": 0}).sort("created_at", -1).to_list(100)


@router.get("/admin/market/config/active")
async def active_config(algorithm: str = "combined", user: dict = Depends(require_staff)):
    row = await db.system_settings.find_one({"kind": "market_configuration", "active": True}, {"_id": 0})
    return row or {"active": False, "version": None, "message": "No active market configuration. Publish one to enable matching and guidance."}


@router.post("/admin/market/config")
async def create_config(payload: dict, user: dict = Depends(require_staff)):
    activate = bool(payload.pop("activate", False))
    row = {"id": new_id(), "kind": "market_configuration", "active": activate, "created_at": now_iso(), **payload}
    if activate:
        await db.system_settings.update_many({"kind": "market_configuration"}, {"$set": {"active": False}})
    await db.system_settings.insert_one(row)
    await db.audit_events.insert_one({
        "id": new_id(), "subject_type": "market_configuration", "subject_id": row["id"],
        "action": "CONFIGURATION_PUBLISHED", "actor_id": user["id"], "created_at": now_iso(),
    })
    row.pop("_id", None)
    return row


@router.post("/admin/market/config/{config_id}/activate")
async def activate_config(config_id: str, user: dict = Depends(require_staff)):
    await db.system_settings.update_many({"kind": "market_configuration"}, {"$set": {"active": False}})
    result = await db.system_settings.update_one({"id": config_id, "kind": "market_configuration"}, {"$set": {"active": True, "activated_at": now_iso()}})
    if not result.matched_count:
        raise HTTPException(404, "Configuration not found")
    await _audit(user, "CONFIGURATION_ACTIVATED", "market_configuration", config_id)
    return {"ok": True}


@router.get("/admin/market/retention/preview")
async def retention_preview(user: dict = Depends(require_staff)):
    return {"summary": {"source_listings": {"eligible": 0}, "observations": {"eligible": 0}},
            "cutoff_at": None, "generated_at": now_iso(), "safe_mode": True,
            "message": "Retention is in safe mode. No evidence records are removed automatically."}


@router.post("/admin/market/retention/run")
async def retention_run(user: dict = Depends(require_staff)):
    return {"ok": True, "removed": 0, "completed_at": now_iso(), "safe_mode": True}


@router.get("/admin/market/scheduler")
async def scheduler(user: dict = Depends(require_staff)):
    return await db.system_settings.find_one({"id": "market_scheduler"}, {"_id": 0}) or {"id": "market_scheduler", "paused": False}


@router.post("/admin/market/scheduler/pause")
async def toggle_scheduler(payload: dict, user: dict = Depends(require_staff)):
    row = {"id": "market_scheduler", "paused": bool(payload.get("paused")), "updated_at": now_iso()}
    await db.system_settings.update_one({"id": "market_scheduler"}, {"$set": row}, upsert=True)
    return row
