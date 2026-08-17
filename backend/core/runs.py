"""Collection Run infrastructure — scraper contract + lifecycle helpers.

Public API:
    async with collection_run(source_id, run_type="manual", triggered_by=user_id) as run:
        for raw in scraper.iter_listings():
            await run.ingest(raw_payload)          # runs full MATCH-1.0 pipeline
        # context exit → auto-finish with success or failed depending on
        # whether an exception escaped, updates source health counters and
        # emits audit events.

Every ingest credits the run's counters (seen / new / updated /
matches_created / review_cases_created). Errors are captured onto the run
document, not thrown, so a partial run stays recoverable and auditable.
"""
from __future__ import annotations

import contextlib
import time
from typing import Any, Optional

from core.db import db, new_id, now_iso
from core.matcher import ingest_market_listing
from models import CollectionRun, MarketAuditEvent


class RunContext:
    """Handle returned by `collection_run`. Exposes `ingest` plus the
    diagnostic recording surface consumed by HttpListingCollector."""

    def __init__(self, run_id: str, source_id: str, actor_id: Optional[str]):
        self.run_id = run_id
        self.source_id = source_id
        self.actor_id = actor_id
        self.seen = 0
        self.new = 0
        self.updated = 0
        self.matches = 0
        self.review_cases = 0
        self.errors: list[str] = []
        # ---- diagnostics ----
        self.diag: dict = {
            "pages_visited": [],
            "cards_seen": 0,
            "cards_accepted": 0,
            "cards_rejected": 0,
            "rejection_reasons": {},
            "detail_urls_identified": 0,
            "detail_pages_attempted": 0,
            "detail_pages_succeeded": 0,
            "detail_pages_failed": 0,
            "pagination_pages_followed": 0,
            "pagination_end_reason": None,
            "duplicate_source_ids_within_run": 0,
            "records_passed_to_ingestion": 0,
            "records_inserted": 0,
            "records_updated": 0,
        }
        self._page_index: dict[str, int] = {}     # url -> index into pages_visited

    # ---------- diagnostic recording ----------
    def record_diag(self, reason: str, *, inc: str | None = None,
                    url: str | None = None, status: int | None = None) -> None:
        # Named-counter bumps first (detail_pages_attempted / _succeeded /
        # _failed, or any other counter passed via `inc`).
        if inc and inc in self.diag:
            self.diag[inc] = int(self.diag.get(inc, 0)) + 1
        # `card_accepted` and `detail_page_*` are non-rejection events —
        # they never bump rejection_reasons and never bump the aggregate
        # cards_* counters. Those aggregates are re-computed from the
        # authoritative `pages_visited` page counters (see `record_page`
        # and `_finalise_run`) so `cards_seen == cards_accepted +
        # cards_rejected` always holds.
        if reason in ("card_accepted", "detail_page_attempted",
                      "detail_page_succeeded"):
            if reason == "detail_page_attempted":
                self.diag["detail_urls_identified"] += 1
            return
        # Duplicate-in-run gets its own dedicated counter so ops can see
        # how many duplicates the scraper deduped this pass; it ALSO
        # counts as a rejection reason for the breakdown view.
        if reason == "duplicate_source_id_within_run":
            self.diag["duplicate_source_ids_within_run"] += 1
        # Everything else is a rejection reason breakdown entry.
        self.diag["rejection_reasons"][reason] = \
            self.diag["rejection_reasons"].get(reason, 0) + 1

    def record_page(self, url: str, cards_seen: int, cards_accepted: int,
                    cards_rejected: int, *, final: bool = False) -> None:
        if url in self._page_index:
            idx = self._page_index[url]
            entry = self.diag["pages_visited"][idx]
            entry.update({"cards_seen": cards_seen,
                          "cards_accepted": cards_accepted,
                          "cards_rejected": cards_rejected,
                          "final": final})
        else:
            self._page_index[url] = len(self.diag["pages_visited"])
            self.diag["pages_visited"].append({
                "url": url,
                "cards_seen": cards_seen,
                "cards_accepted": cards_accepted,
                "cards_rejected": cards_rejected,
                "final": final,
            })
        if final:
            self.diag["pagination_pages_followed"] = len(self.diag["pages_visited"])
            self.diag["cards_seen"] = sum(p.get("cards_seen", 0) for p in self.diag["pages_visited"])
            self.diag["cards_accepted"] = sum(p.get("cards_accepted", 0) for p in self.diag["pages_visited"])
            self.diag["cards_rejected"] = sum(p.get("cards_rejected", 0) for p in self.diag["pages_visited"])

    def record_pagination_end(self, reason: str) -> None:
        # Preserve first end-reason if already set
        self.diag["pagination_end_reason"] = self.diag["pagination_end_reason"] or reason

    async def ingest(self, payload: dict) -> dict:
        """Ingest one listing under this run. Never raises — errors get
        appended to the run's error list so the whole batch keeps going."""
        payload = {**payload, "source_id": self.source_id}
        self.seen += 1
        self.diag["records_passed_to_ingestion"] += 1
        try:
            result = await ingest_market_listing(payload, actor_id=self.actor_id)
        except Exception as e:  # noqa: BLE001 — scraper must not crash the whole run
            msg = f"{payload.get('source_listing_id') or '?'}: {type(e).__name__}: {e}"
            self.errors.append(msg[:500])
            return {"error": msg}

        if result.get("is_new"):
            self.new += 1
            self.diag["records_inserted"] += 1
        else:
            self.updated += 1
            self.diag["records_updated"] += 1
        if result.get("match"):
            self.matches += 1
        if result.get("review_case"):
            self.review_cases += 1

        # Continuously flush counters + diagnostics so live dashboards see progress
        await db.collection_runs.update_one(
            {"id": self.run_id},
            {"$set": {
                "listings_seen": self.seen,
                "listings_new": self.new,
                "listings_updated": self.updated,
                "matches_created": self.matches,
                "review_cases_created": self.review_cases,
                "diagnostics": self.diag,
            }},
        )
        return result


@contextlib.asynccontextmanager
async def collection_run(source_id: str, *, run_type: str = "manual",
                         triggered_by: Optional[str] = None,
                         parser_version: Optional[str] = None):
    """Start a run, hand back a `RunContext`, then auto-close on exit."""
    source = await db.market_sources.find_one({"id": source_id}, {"_id": 0})
    if not source:
        raise ValueError(f"source_id {source_id} not found")

    run = CollectionRun(
        source_id=source_id, run_type=run_type, triggered_by=triggered_by,
        parser_version=parser_version or source.get("parser_version"),
    ).model_dump()
    await db.collection_runs.insert_one(run)
    run.pop("_id", None)

    ctx = RunContext(run["id"], source_id, triggered_by)
    started_wall = time.monotonic()
    fatal: Optional[BaseException] = None
    try:
        yield ctx
    except BaseException as e:                # noqa: BLE001 — capture, re-raise after finalise
        fatal = e
    finally:
        await _finalise_run(run["id"], source_id, ctx, fatal,
                            started_wall, triggered_by)
    if fatal:
        raise fatal


async def _finalise_run(run_id: str, source_id: str, ctx: RunContext,
                        fatal: Optional[BaseException],
                        started_wall: float, actor_id: Optional[str]) -> None:
    duration_ms = int((time.monotonic() - started_wall) * 1000)
    status = "success"
    if fatal is not None:
        status = "failed"
        ctx.errors.append(f"fatal: {type(fatal).__name__}: {fatal}"[:500])
    elif ctx.errors:
        status = "partial"

    # ---- Reconcile run-level card counters against per-page authority ----
    # The pages_visited entries are the ground truth (each card is counted
    # exactly once as either accepted or rejected inside `_walk_category`).
    # The event-based counters bumped in `record_diag` can drift (e.g. a
    # detail-page rejection also increments a rejection reason), which
    # historically produced `cards_accepted + cards_rejected > cards_seen`
    # at run level. Overwrite them with the authoritative page sums.
    pages = ctx.diag.get("pages_visited") or []
    if pages:
        ctx.diag["cards_seen"] = sum(int(p.get("cards_seen") or 0) for p in pages)
        ctx.diag["cards_accepted"] = sum(int(p.get("cards_accepted") or 0) for p in pages)
        ctx.diag["cards_rejected"] = sum(int(p.get("cards_rejected") or 0) for p in pages)
        ctx.diag["pagination_pages_followed"] = len(pages)

    now = now_iso()
    await db.collection_runs.update_one(
        {"id": run_id},
        {"$set": {
            "finished_at": now, "duration_ms": duration_ms,
            "status": status, "errors": ctx.errors,
            "listings_seen": ctx.seen, "listings_new": ctx.new,
            "listings_updated": ctx.updated,
            "matches_created": ctx.matches,
            "review_cases_created": ctx.review_cases,
            "diagnostics": ctx.diag,
        }},
    )

    # Source health counters
    source_patch: dict[str, Any] = {"last_run_at": now, "updated_at": now}
    if status == "success":
        source_patch["last_successful_run_at"] = now
        source_patch["consecutive_failures"] = 0
    elif status == "failed":
        source = await db.market_sources.find_one({"id": source_id}, {"_id": 0}) or {}
        source_patch["consecutive_failures"] = int(source.get("consecutive_failures", 0)) + 1
    else:  # partial — count once but don't reset streak
        source = await db.market_sources.find_one({"id": source_id}, {"_id": 0}) or {}
        source_patch["consecutive_failures"] = int(source.get("consecutive_failures", 0))
    await db.market_sources.update_one({"id": source_id}, {"$set": source_patch})

    # Audit event summarising the run
    ev = MarketAuditEvent(
        event_type=f"run_{status}",
        entity_type="collection_run",
        entity_id=run_id,
        payload={"source_id": source_id, "seen": ctx.seen, "new": ctx.new,
                 "updated": ctx.updated, "matches": ctx.matches,
                 "review_cases": ctx.review_cases, "duration_ms": duration_ms,
                 "errors": len(ctx.errors)},
        actor_id=actor_id,
        algorithm_version="MATCH-1.0",
    ).model_dump()
    await db.market_audit_events.insert_one(ev)


# ---------------- health metrics ----------------
async def source_health(source_id: str, window: int = 10) -> dict:
    """Aggregate the last N runs into a health summary."""
    runs = await db.collection_runs.find(
        {"source_id": source_id}, {"_id": 0},
    ).sort("started_at", -1).to_list(window)
    if not runs:
        return {"source_id": source_id, "runs": 0, "success_rate": None,
                "error_rate": None, "last_run_at": None,
                "last_successful_run_at": None}
    ok = sum(1 for r in runs if r["status"] == "success")
    fail = sum(1 for r in runs if r["status"] == "failed")
    partial = sum(1 for r in runs if r["status"] == "partial")
    src = await db.market_sources.find_one({"id": source_id}, {"_id": 0}) or {}
    return {
        "source_id": source_id,
        "runs": len(runs),
        "success_rate": round(ok / len(runs) * 100, 1),
        "error_rate": round(fail / len(runs) * 100, 1),
        "partial_rate": round(partial / len(runs) * 100, 1),
        "last_run_at": src.get("last_run_at"),
        "last_successful_run_at": src.get("last_successful_run_at"),
        "consecutive_failures": int(src.get("consecutive_failures", 0)),
        "avg_duration_ms": round(
            sum(r.get("duration_ms") or 0 for r in runs) / len(runs), 0,
        ),
        "listings_last_run": (runs[0].get("listings_seen") or 0) if runs else 0,
    }
