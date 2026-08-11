"""Scraper Scheduler — background task that periodically fires
`collection_run` for every active source whose `collection_frequency` is
past its last successful run.

Runs as a single asyncio background task started from `server.py` on
application startup. Simple, dependency-free (no APScheduler), tick every
`SCHEDULER_TICK_SECONDS` (default 60s), enforces per-source cooldowns
based on frequency.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from core.collectors import get_collector
from core.db import db
from core.runs import collection_run

logger = logging.getLogger(__name__)

FREQUENCY_SECONDS = {
    "hourly": 3600,
    "daily": 86400,
    "weekly": 7 * 86400,
}
TICK_SECONDS = int(os.environ.get("SCHEDULER_TICK_SECONDS", "60"))

# Module-level task so we don't start two loops if uvicorn reloads.
_task: Optional[asyncio.Task] = None
_paused: bool = os.environ.get("SCHEDULER_PAUSED", "false").lower() == "true"


def _parse_iso(v: Optional[str]) -> Optional[datetime]:
    if not v:
        return None
    try:
        dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


async def _run_one(source: dict) -> None:
    key = source.get("collector") or "seed"
    Collector = get_collector(key)
    if not Collector:
        logger.warning(f"Scheduler: source {source['name']} has unknown collector '{key}'")
        return
    logger.info(f"Scheduler: firing {key} for source {source['name']}")
    collector = Collector(source)
    async with collection_run(source["id"], run_type="scheduled",
                               triggered_by="scheduler",
                               parser_version=source.get("parser_version")) as run:
        async for payload in collector.iter_listings():
            await run.ingest(payload)


async def _tick() -> None:
    global _paused
    if _paused:
        return
    # Retention runs once per day regardless of scheduler tick frequency
    try:
        from core.retention import run_retention_if_due
        await run_retention_if_due()
    except Exception as e:                                              # noqa: BLE001
        logger.exception(f"Retention tick failed: {e}")

    now = datetime.now(timezone.utc)
    async for src in db.market_sources.find({"active": True}, {"_id": 0}):
        freq = src.get("collection_frequency") or "manual"
        if freq not in FREQUENCY_SECONDS:
            continue
        last = _parse_iso(src.get("last_successful_run_at"))
        cooldown = FREQUENCY_SECONDS[freq]
        # Slower after consecutive failures — exponential back-off (cap 6x)
        streak = int(src.get("consecutive_failures") or 0)
        cooldown *= max(1, min(6, streak + 1))
        if last is None or (now - last) >= timedelta(seconds=cooldown):
            try:
                await _run_one(src)
            except Exception as e:                                     # noqa: BLE001
                logger.exception(f"Scheduler run failed for {src['name']}: {e}")


async def _loop() -> None:
    logger.info(f"Scheduler started (tick={TICK_SECONDS}s, paused={_paused})")
    while True:
        try:
            await _tick()
        except Exception as e:                                          # noqa: BLE001
            logger.exception(f"Scheduler tick crashed: {e}")
        await asyncio.sleep(TICK_SECONDS)


def start_scheduler() -> None:
    global _task
    if _task and not _task.done():
        return
    _task = asyncio.create_task(_loop(), name="market-scheduler")


def scheduler_state() -> dict:
    return {
        "paused": _paused,
        "tick_seconds": TICK_SECONDS,
        "task_running": bool(_task and not _task.done()),
    }


def set_paused(value: bool) -> None:
    global _paused
    _paused = bool(value)
