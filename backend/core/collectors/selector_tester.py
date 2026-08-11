"""Selector tester — generic edition.

Backs the admin "Inspect" button on the Data Sources page. Given a collector
key + URL, fetches the page, runs every field selector against the configured
card grid, and reports per-field match counts + up to 3 sample values. This
lets ops tune each site's `parser_config` without waiting on a full collection
run.

Works for every `HttpListingCollector` subclass (hausples_png, ljhookerpng,
mypnghome, sre, dac, marketmeri). The `hausples_tester.probe_hausples`
function is now a thin wrapper around this for backward compatibility.
"""
from __future__ import annotations

from typing import Optional

import httpx

from core.collectors import get_collector
from core.collectors._common import (
    HttpListingCollector,
    parse_price,
    text_of,
)

try:
    from selectolax.parser import HTMLParser
    _HAVE_SELECTOLAX = True
except ImportError:                                                     # pragma: no cover
    _HAVE_SELECTOLAX = False


FIELD_KEYS = ["url", "title", "price", "address", "description",
              "beds", "baths", "land", "building"]


def collector_defaults(key: str) -> Optional[dict]:
    """Return the DEFAULT_CONFIG for a registered HTTP collector, or None
    if the key doesn't exist or isn't an HTTP collector."""
    Coll = get_collector(key)
    if not Coll or not issubclass(Coll, HttpListingCollector):
        return None
    return dict(Coll.DEFAULT_CONFIG)


async def probe_collector(key: str, url: str,
                          selectors: dict | None = None) -> dict:
    """Fetch `url` and grade the selectors against it. Non-fatal — network
    errors surface on the `error` key."""
    defaults = collector_defaults(key)
    if defaults is None:
        return {"ok": False, "url": url,
                "error": f"Unknown collector '{key}' (must be an HTTP collector)"}
    if not _HAVE_SELECTOLAX:                                            # pragma: no cover
        return {"ok": False, "url": url,
                "error": "selectolax not installed"}

    cfg = dict(defaults)
    if selectors:
        # Only accept keys we know about — filter noise.
        cfg.update({k: v for k, v in selectors.items()
                    if k in defaults and v})

    headers = {"User-Agent": cfg.get("user_agent",
                                     "TREL-Aggregator/1.0 (+https://trel.com.pg)")}
    try:
        async with httpx.AsyncClient(timeout=15.0, headers=headers,
                                     follow_redirects=True) as client:
            r = await client.get(url)
            r.raise_for_status()
            html = r.text
    except Exception as e:                                              # noqa: BLE001
        return {"ok": False, "url": url,
                "error": f"{type(e).__name__}: {e}"}

    tree = HTMLParser(html)
    cards = tree.css(cfg["card"])

    per_field: dict[str, dict] = {}
    for k in FIELD_KEYS:
        sel = cfg.get(k)
        if not sel:
            per_field[k] = {"selector": None, "matches": 0,
                            "match_rate": 0.0, "samples": []}
            continue
        matches = 0
        samples: list[str] = []
        for card in cards:
            node = card.css_first(sel)
            if node is None:
                continue
            matches += 1
            if k == "url":
                v = (node.attributes.get("href") or "").strip()
            elif k in ("price", "land", "building"):
                raw = text_of(node)
                num = parse_price(raw)
                v = f"{raw}  →  {num}"
            else:
                v = text_of(node)
            if v and len(samples) < 3:
                samples.append(v)
        per_field[k] = {"selector": sel, "matches": matches,
                        "match_rate": round(matches / len(cards) * 100, 1) if cards else 0.0,
                        "samples": samples}

    return {
        "ok": True,
        "collector": key,
        "url": url,
        "http_status": 200,
        "html_bytes": len(html),
        "card_selector": cfg["card"],
        "cards_found": len(cards),
        "fields": per_field,
    }
