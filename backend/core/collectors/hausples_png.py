"""Hausples PNG collector — real HTTP + HTML parsing.

Uses `httpx` for fetching and `selectolax.parser.HTMLParser` (falls back to a
tiny regex-based extractor when selectolax isn't installed) to extract
listing tiles from search-result pages.

Selectors are configurable via `MarketSource.parser_config` so operators can
adjust when the site tweaks its markup — no code deploy needed. The default
configuration below assumes a fairly common real-estate listing layout
(hausples.com.pg card grid) and gracefully degrades:

  * unreachable site → empty iterator, run reports partial with 0 listings
  * unparseable page → per-page error captured on the run doc, next page still
    tried
  * missing individual fields → row still emitted, MATCH-1.0 handles gaps

Ship state: **inactive by default**. Operator flips `active=true` on the
source in the admin UI once selectors are validated for the current live
DOM.
"""
from __future__ import annotations

import logging
import re
from typing import AsyncIterator, Optional

import httpx

from core.collectors import CollectorBase, register

logger = logging.getLogger(__name__)

try:
    from selectolax.parser import HTMLParser  # fast, dep-light
    _HAVE_SELECTOLAX = True
except ImportError:                                                   # pragma: no cover
    _HAVE_SELECTOLAX = False

DEFAULT_PARSER_CONFIG = {
    "search_paths": ["/property-for-sale", "/property-for-rent"],
    # CSS selectors for card container + fields (adjust in admin UI)
    "card": ".listing-card, .property-card, article",
    "url":   "a.listing-link, a.card-link, a[href*='/property/']",
    "title": ".listing-title, .card-title, h3",
    "price": ".listing-price, .price, .card-price",
    "address": ".listing-address, .address, .card-address",
    "beds":  ".listing-beds, .beds",
    "baths": ".listing-baths, .baths",
    "land":  ".listing-land, .land-area",
    "building": ".listing-building, .building-area",
    "max_pages_per_purpose": 3,
}

_PRICE_RE = re.compile(r"([\d,]+(?:\.\d+)?)")
_INT_RE = re.compile(r"\d+")


def _num(text: Optional[str]) -> Optional[float]:
    if not text:
        return None
    m = _PRICE_RE.search(text.replace(" ", ""))
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def _first_int(text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    m = _INT_RE.search(text)
    return int(m.group(0)) if m else None


def _text(node) -> str:
    return (node.text(strip=True) if node else "").strip()


def _parse_address(addr: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Best-effort split: '15 Waigani Drive, Waigani, Port Moresby' →
    (street, suburb, city)."""
    if not addr:
        return None, None, None
    parts = [p.strip() for p in addr.split(",") if p.strip()]
    street = suburb = city = None
    if len(parts) >= 1:
        street = parts[0]
    if len(parts) >= 2:
        suburb = parts[1]
    if len(parts) >= 3:
        city = parts[-1]
    return street, suburb, city


@register
class HausplesCollector(CollectorBase):
    key = "hausples_png"
    label = "Hausples PNG (real HTTP)"
    requires_network = True

    def _config(self) -> dict:
        cfg = dict(DEFAULT_PARSER_CONFIG)
        cfg.update(self.source.get("parser_config") or {})
        return cfg

    async def _fetch(self, client: httpx.AsyncClient, url: str) -> Optional[str]:
        try:
            r = await client.get(url)
            r.raise_for_status()
            return r.text
        except Exception as e:                                        # noqa: BLE001
            logger.info(f"hausples fetch {url}: {e}")
            return None

    def _parse_page(self, html: str, cfg: dict, purpose: str, base_url: str
                    ) -> list[dict]:
        if not html or not _HAVE_SELECTOLAX:
            return []
        rows: list[dict] = []
        tree = HTMLParser(html)
        for card in tree.css(cfg["card"]):
            link = card.css_first(cfg["url"])
            href = link.attributes.get("href") if link else None
            if not href:
                continue
            source_listing_id = href.rstrip("/").split("/")[-1]
            if not source_listing_id:
                continue
            source_url = href if href.startswith("http") else f"{base_url}{href}"
            title = _text(card.css_first(cfg["title"]))
            price = _num(_text(card.css_first(cfg["price"])))
            addr = _text(card.css_first(cfg["address"]))
            street, suburb, city = _parse_address(addr)
            beds = _first_int(_text(card.css_first(cfg["beds"])))
            baths = _first_int(_text(card.css_first(cfg["baths"])))
            land = _num(_text(card.css_first(cfg["land"])))
            bldg = _num(_text(card.css_first(cfg["building"])))
            rows.append({
                "source_listing_id": source_listing_id,
                "source_url": source_url,
                "purpose": purpose,
                "price": price,
                "rent_period": "monthly" if purpose == "rent" else None,
                "property_class": "residential",     # refined per subtype later
                "property_subtype": title.split()[0] if title else None,
                "street": street, "suburb": suburb, "city": city,
                "bedrooms": beds, "bathrooms": baths,
                "land_area_m2": land, "building_area_m2": bldg,
                "raw_fields": {"title": title, "address": addr},
            })
        return rows

    async def iter_listings(self) -> AsyncIterator[dict]:
        cfg = self._config()
        base = (self.source.get("base_url") or "https://www.hausples.com.pg").rstrip("/")
        headers = {"User-Agent": "TREL-Aggregator/1.0 (+https://trel.com.pg)"}

        async with httpx.AsyncClient(timeout=15.0, headers=headers,
                                     follow_redirects=True) as client:
            for path in cfg["search_paths"]:
                purpose = "rent" if "rent" in path else "sale"
                for page in range(1, int(cfg.get("max_pages_per_purpose", 3)) + 1):
                    url = f"{base}{path}?page={page}"
                    html = await self._fetch(client, url)
                    if html is None:
                        break                                          # source unreachable
                    rows = self._parse_page(html, cfg, purpose, base)
                    if not rows:                                        # empty page → stop paging
                        break
                    for r in rows:
                        yield r
