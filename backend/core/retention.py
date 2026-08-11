"""Retention Enforcement — soft-delete rows past their retention window.

Runs once every 24h via the scheduler's periodic tick (`run_retention_if_due`).
Reads windows from the active configuration's `retention` block. Every archival
emits a summary audit event so operators can see what was purged.

Soft-delete = set `archived_at` timestamp + `archived_by:"retention_policy"`.
Hard-delete happens only when `soft_delete_only=false` in the config.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from core.db import db, now_iso
from models import MarketAuditEvent

logger = logging.getLogger(__name__)

# Cache: only run retention once every 24h regardless of scheduler tick freq
_LAST_RUN_KEY = "retention_last_run"
RUN_EVERY_SECONDS = int(os.environ.get("RETENTION_EVERY_SECONDS", str(24 * 3600)))

# Collection → retention key mapping
COLLECTIONS = {
    "market_listing_snapshots": "raw_source_data_days",
    "market_listings":          "normalized_data_days",
    "market_review_cases":      "review_case_days",
    "market_audit_events":      "audit_log_days",
    "collection_runs":          "raw_source_data_days",
}
# Extra guard — audit events beyond audit_log_days are the last thing anyone
# should hard-delete. Force soft-delete regardless of policy.
FORCE_SOFT = {"market_audit_events"}


async def _active_retention() -> Optional[dict]:
    cfg = await db.market_configuration.find_one(
        {"active": True, "algorithm": {"$in": ["combined", "guidance"]}}, {"_id": 0},
    )
    if not cfg:
        return None
    return cfg["parameters"].get("retention")


async def preview_retention() -> dict:
    """Dry-run counterpart to `run_retention` — reports how many rows WOULD
    be archived under the current retention config without touching data.
    Powers the 'Preview impact' button on the Retention tab so operators
    can see the blast radius before flipping any switch."""
    retention = await _active_retention()
    if not retention:
        return {"skipped": True, "reason": "no_active_config"}
    soft_only = bool(retention.get("soft_delete_only", True))

    now = datetime.now(timezone.utc)
    summary: dict[str, dict] = {}
    for coll, window_key in COLLECTIONS.items():
        days = int(retention.get(window_key) or 0)
        if days <= 0:
            summary[coll] = {"candidates": 0, "window_days": 0, "action": "disabled"}
            continue
        cutoff = (now - timedelta(days=days)).isoformat()
        query = {
            "created_at": {"$lt": cutoff},
            "$or": [{"archived_at": {"$exists": False}}, {"archived_at": None}],
        }
        candidates = await db[coll].count_documents(query)
        action = "soft_delete" if (soft_only or coll in FORCE_SOFT) else "hard_delete"
        summary[coll] = {"candidates": candidates, "window_days": days, "action": action}
    return {"skipped": False, "soft_delete_only": soft_only,
            "summary": summary, "previewed_at": now_iso()}


async def run_retention(force: bool = False, actor_id: Optional[str] = None) -> dict:
    """Do a single retention pass. Returns a summary dict."""
    retention = await _active_retention()
    if not retention:
        return {"skipped": True, "reason": "no_active_config"}
    soft_only = bool(retention.get("soft_delete_only", True))

    now = datetime.now(timezone.utc)
    summary: dict[str, dict] = {}

    for coll, window_key in COLLECTIONS.items():
        days = int(retention.get(window_key) or 0)
        if days <= 0:
            continue
        cutoff = (now - timedelta(days=days)).isoformat()
        # Only touch rows created before the cutoff AND not already archived
        query = {
            "created_at": {"$lt": cutoff},
            "$or": [{"archived_at": {"$exists": False}}, {"archived_at": None}],
        }
        col = db[coll]
        count_candidate = await col.count_documents(query)
        if soft_only or coll in FORCE_SOFT:
            r = await col.update_many(
                query,
                {"$set": {"archived_at": now_iso(),
                          "archived_by": "retention_policy",
                          "retention_days": days}},
            )
            summary[coll] = {"soft_deleted": r.modified_count,
                             "candidates": count_candidate,
                             "window_days": days}
        else:
            r = await col.delete_many(query)
            summary[coll] = {"hard_deleted": r.deleted_count,
                             "candidates": count_candidate,
                             "window_days": days}

    ev = MarketAuditEvent(
        event_type="retention_run",
        entity_type="retention_policy",
        payload={"soft_delete_only": soft_only, "summary": summary,
                 "forced": force},
        actor_id=actor_id or "retention_policy",
    ).model_dump()
    await db.market_audit_events.insert_one(ev)
    logger.info(f"Retention run complete: {summary}")
    return {"skipped": False, "soft_delete_only": soft_only, "summary": summary,
            "ran_at": now_iso()}


async def run_retention_if_due() -> Optional[dict]:
    """Called from the scheduler tick. Runs only if RUN_EVERY_SECONDS have
    passed since the last run (tracked in a Mongo key/value doc)."""
    now = datetime.now(timezone.utc)
    marker = await db.system_state.find_one({"key": _LAST_RUN_KEY}, {"_id": 0})
    last = None
    if marker and marker.get("value"):
        try:
            last = datetime.fromisoformat(marker["value"].replace("Z", "+00:00"))
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
        except Exception:
            last = None
    if last and (now - last).total_seconds() < RUN_EVERY_SECONDS:
        return None
    out = await run_retention()
    await db.system_state.update_one(
        {"key": _LAST_RUN_KEY},
        {"$set": {"key": _LAST_RUN_KEY, "value": now_iso()}},
        upsert=True,
    )
    return out
