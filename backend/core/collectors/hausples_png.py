"""Hausples PNG collector — best-effort adapter for hausples.com.pg.

Uses `httpx` (already in requirements) with strict timeouts. Failures are
non-fatal thanks to the RunContext contract in `core.runs`. Ships DISABLED
until an operator explicitly turns on the source (`active=true`) — the
seed collector runs by default.

Note: this is a scaffold. Real HTML parsing selectors will need updating if
Hausples change their DOM. For Phase 1 we return an empty iterator when the
site is unreachable so the run still completes cleanly.
"""
from __future__ import annotations

import logging
from typing import AsyncIterator

import httpx

from core.collectors import CollectorBase, register

logger = logging.getLogger(__name__)


@register
class HausplesCollector(CollectorBase):
    key = "hausples_png"
    label = "Hausples PNG (real HTTP)"
    requires_network = True

    async def iter_listings(self) -> AsyncIterator[dict]:
        base = self.source.get("base_url") or "https://www.hausples.com.pg"
        headers = {"User-Agent": "TREL-Aggregator/1.0 (+https://trel.com.pg)"}
        try:
            async with httpx.AsyncClient(timeout=10.0, headers=headers, follow_redirects=True) as client:
                # For the phase-1 scaffold we just probe the site — anything more
                # requires stable DOM selectors we don't want to guess at here.
                r = await client.get(base)
                r.raise_for_status()
        except Exception as e:                                    # noqa: BLE001
            logger.info(f"Hausples collector probe failed: {e}")
            return                                                # yield nothing
        # TODO(phase-E): implement listing search + parse when Hausples HTML
        # is stable. Framework already handles updates + snapshots via
        # source_listing_id, so parsing changes drop in without pipeline
        # changes.
        if False:
            yield {}                                              # for typing
