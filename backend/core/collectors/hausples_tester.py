"""Legacy shim — kept for backward compatibility with existing callers
(the `/admin/market/collectors/hausples_png/test` endpoint delegates through
here). All real work now lives in `selector_tester.probe_collector`, which
works for every HTTP collector."""
from __future__ import annotations

from core.collectors.selector_tester import (
    collector_defaults,
    probe_collector,
)

# Preserved for older imports.
DEFAULT_PARSER_CONFIG = collector_defaults("hausples_png") or {}


async def probe_hausples(url: str, selectors: dict | None = None) -> dict:
    return await probe_collector("hausples_png", url, selectors)
