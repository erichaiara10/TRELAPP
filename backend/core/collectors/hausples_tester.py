"""Selector tester — fetches an arbitrary Hausples URL and reports which
CSS selectors matched (with samples) so operators can tune the parser
config without waiting on a full collection run.

Powers `POST /api/admin/market/collectors/hausples_png/test`.
"""
from __future__ import annotations

import httpx
from selectolax.parser import HTMLParser

from core.collectors._common import parse_price as _num, text_of as _text
from core.collectors.hausples_png import HausplesCollector


DEFAULT_PARSER_CONFIG = HausplesCollector.DEFAULT_CONFIG


async def probe_hausples(url: str, selectors: dict | None = None) -> dict:
    """Fetch the URL, run every configured selector, return match counts +
    up to 3 sample values per selector. Non-fatal — network errors surface
    on `error` key."""
    cfg = dict(DEFAULT_PARSER_CONFIG)
    if selectors:
        cfg.update({k: v for k, v in selectors.items()
                    if k in DEFAULT_PARSER_CONFIG and v})

    headers = {"User-Agent": "TREL-Aggregator/1.0 (+https://trel.com.pg)"}
    try:
        async with httpx.AsyncClient(timeout=15.0, headers=headers,
                                     follow_redirects=True) as client:
            r = await client.get(url)
            r.raise_for_status()
            html = r.text
    except Exception as e:
        return {"ok": False, "url": url, "error": f"{type(e).__name__}: {e}"}

    tree = HTMLParser(html)
    cards = tree.css(cfg["card"])
    field_keys = ["url", "title", "price", "address", "beds", "baths", "land", "building"]

    per_field: dict[str, dict] = {}
    for k in field_keys:
        sel = cfg[k]
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
                raw = _text(node)
                num = _num(raw)
                v = f"{raw}  →  {num}"
            else:
                v = _text(node)
            if v and len(samples) < 3:
                samples.append(v)
        per_field[k] = {"selector": sel, "matches": matches,
                        "match_rate": round(matches / len(cards) * 100, 1) if cards else 0.0,
                        "samples": samples}

    return {
        "ok": True,
        "url": url,
        "http_status": 200,
        "html_bytes": len(html),
        "card_selector": cfg["card"],
        "cards_found": len(cards),
        "fields": per_field,
    }
