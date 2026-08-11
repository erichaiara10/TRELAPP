"""Shared building blocks for PNG real-estate HTML collectors.

Every collector in this package (hausples, ljhookerpng, mypnghome, sre,
dac, marketmeri) plugs the same tiny primitives:

* `HttpListingCollector` — a generic base that walks paginated search pages,
  extracts a card grid, and yields normalised listing dicts. Concrete
  collectors just declare their default selectors + purpose paths.
* `parse_allotment_section(text)` — teases out Allotment/Lot + Section numbers
  from free-text titles or descriptions (PNG listings frequently write
  "Allotment 14 Section 27 Waigani" or "Lot 5, Sec 9, Boroko").
* `parse_address(addr)` — best-effort split of "12 Main St, Gordons, Port
  Moresby" into (street, suburb, city).
* `parse_price(text)` — pulls the first big number out of a price cell.

All values are optional — the MATCH-1.0 pipeline handles gaps gracefully.
"""
from __future__ import annotations

import logging
import re
from typing import AsyncIterator, Optional

import httpx

from core.collectors import CollectorBase

logger = logging.getLogger(__name__)

try:
    from selectolax.parser import HTMLParser
    _HAVE_SELECTOLAX = True
except ImportError:                                                    # pragma: no cover
    _HAVE_SELECTOLAX = False


# ---------------------------------------------------------------------
# Regex primitives
# ---------------------------------------------------------------------
_PRICE_RE = re.compile(r"([\d,]+(?:\.\d+)?)")
_INT_RE = re.compile(r"\d+")

# "Allotment 14 Section 27" | "Lot 5 Section 9" | "Alloc 14 / Sec 27" | "Lot 5, Sec 9"
_ALLOT_RE = re.compile(
    r"(?:allotment|allot|alloc|lot)[\s._-]*(\d+[A-Za-z]?)"
    r"[\s,._/-]+(?:section|sec)[\s._-]*(\d+[A-Za-z]?)",
    re.IGNORECASE,
)
# Reverse form: "Section 27 Allotment 14"
_SECT_ALLOT_RE = re.compile(
    r"(?:section|sec)[\s._-]*(\d+[A-Za-z]?)"
    r"[\s,._/-]+(?:allotment|allot|alloc|lot)[\s._-]*(\d+[A-Za-z]?)",
    re.IGNORECASE,
)
# "Portion 1234" (customary land)
_PORTION_RE = re.compile(r"portion[\s._-]*(\d+[A-Za-z]?)", re.IGNORECASE)

# Bedroom/bathroom short-hands frequently used inline: "3 bed 2 bath", "3br 2ba"
_BEDS_RE = re.compile(r"(\d+)\s*(?:br|bd|bed|bedroom)", re.IGNORECASE)
_BATHS_RE = re.compile(r"(\d+)\s*(?:ba|bth|bath|bathroom)", re.IGNORECASE)

# Subtype hints (lowercase compare)
_SUBTYPE_HINTS = [
    # Compound / more-specific keywords go BEFORE the generic ones so
    # "warehouse" doesn't get shadowed by "house", "townhouse" by "house", etc.
    ("warehouse", "commercial_industrial", "Warehouse"),
    ("townhouse", "residential", "Townhouse"),
    ("apartment", "residential", "Apartment"),
    ("unit",      "residential", "Apartment"),
    ("duplex",    "residential", "Duplex"),
    ("villa",     "residential", "Villa"),
    ("house",     "residential", "House"),
    ("factory",   "commercial_industrial", "Warehouse"),
    ("office",    "commercial_industrial", "Office"),
    ("retail",    "commercial_industrial", "Retail Space"),
    ("shop",      "commercial_industrial", "Retail Space"),
    ("commercial", "commercial_industrial", "Office"),
    ("industrial", "commercial_industrial", "Warehouse"),
    ("land",      "vacant_land", "Vacant Land"),
    ("block",     "vacant_land", "Vacant Land"),
]


# ---------------------------------------------------------------------
# Text extractors
# ---------------------------------------------------------------------
def parse_price(text: Optional[str]) -> Optional[float]:
    if not text:
        return None
    cleaned = text.replace(" ", "").replace("PGK", "").replace("K", "").replace("$", "")
    m = _PRICE_RE.search(cleaned)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def first_int(text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    m = _INT_RE.search(text)
    return int(m.group(0)) if m else None


def parse_allotment_section(text: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Return (allotment_number, section_number) extracted from any free-text
    field. Handles both `Allotment X Section Y` and `Section Y Allotment X`
    orderings, plus common abbreviations."""
    if not text:
        return None, None
    m = _ALLOT_RE.search(text)
    if m:
        return m.group(1), m.group(2)
    m = _SECT_ALLOT_RE.search(text)
    if m:
        return m.group(2), m.group(1)         # (allotment, section)
    return None, None


def parse_portion(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    m = _PORTION_RE.search(text)
    return m.group(1) if m else None


def parse_bedrooms(text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    m = _BEDS_RE.search(text)
    return int(m.group(1)) if m else None


def parse_bathrooms(text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    m = _BATHS_RE.search(text)
    return int(m.group(1)) if m else None


def parse_address(addr: Optional[str]) -> tuple[Optional[str], Optional[str],
                                                Optional[str], Optional[str]]:
    """Best-effort split of `12 Main St, Gordons, Port Moresby, NCD` →
    (street, suburb, city, province)."""
    if not addr:
        return None, None, None, None
    parts = [p.strip() for p in addr.split(",") if p.strip()]
    street = parts[0] if len(parts) >= 1 else None
    suburb = parts[1] if len(parts) >= 2 else None
    city   = parts[2] if len(parts) >= 3 else None
    prov   = parts[3] if len(parts) >= 4 else None
    return street, suburb, city, prov


def infer_subtype(*texts: str) -> tuple[Optional[str], Optional[str]]:
    """Guess property_class + property_subtype from any snippet of text."""
    hay = " ".join((t or "").lower() for t in texts)
    for kw, cls, sub in _SUBTYPE_HINTS:
        if kw in hay:
            return cls, sub
    return None, None


def text_of(node) -> str:
    return (node.text(strip=True) if node else "").strip()


def attr_of(node, name: str) -> Optional[str]:
    if not node:
        return None
    return node.attributes.get(name)


# ---------------------------------------------------------------------
# Base HTTP + HTML collector
# ---------------------------------------------------------------------
class HttpListingCollector(CollectorBase):
    """Skeleton every network-backed collector inherits. Subclasses set
    class-level `DEFAULT_CONFIG` (see the concrete collector files for
    shape). All selectors + paths are overridable at run-time via
    `MarketSource.parser_config`, so operators can adjust when a site
    tweaks its markup."""

    requires_network = True
    DEFAULT_CONFIG: dict = {}       # subclass fills

    def _config(self) -> dict:
        cfg = dict(self.DEFAULT_CONFIG)
        cfg.update(self.source.get("parser_config") or {})
        return cfg

    def _base_url(self) -> str:
        # Fall back to the collector's default host if the source itself
        # doesn't override it (keeps demo data setups friction-free).
        return (self.source.get("base_url")
                or self.DEFAULT_CONFIG.get("base_url", "")).rstrip("/")

    def _pagination_url(self, cfg: dict, path: str, page: int) -> str:
        """Slot page number into the search URL. Two flavours supported:

        * `template` mode — `cfg['page_url_template']` with `{path}` and
          `{page}` placeholders (needed by mypnghome, ljhooker etc that use
          `/page/N/`).
        * `query` mode (default) — simply appends `?page=N`.
        """
        base = self._base_url()
        tpl = cfg.get("page_url_template")
        if tpl:
            return tpl.format(base=base, path=path, page=page)
        sep = "&" if "?" in path else "?"
        return f"{base}{path}{sep}page={page}"

    async def _fetch(self, client: httpx.AsyncClient, url: str) -> Optional[str]:
        try:
            r = await client.get(url)
            r.raise_for_status()
            return r.text
        except Exception as e:                                          # noqa: BLE001
            logger.info(f"{self.key} fetch {url}: {e}")
            return None

    def _parse_card(self, card, cfg: dict, purpose: str,
                    base_url: str) -> Optional[dict]:
        """Extract a single listing tile. Returns None if the card is
        unusable (no URL / no ID). Subclasses can override for site-specific
        quirks."""
        if not _HAVE_SELECTOLAX:
            return None

        link = card.css_first(cfg["url"]) if cfg.get("url") else None
        href = attr_of(link, "href")
        if not href:
            return None
        source_url = href if href.startswith("http") else f"{base_url}{href}"
        source_listing_id = href.rstrip("/").split("/")[-1] or href
        if not source_listing_id or source_listing_id in {"#", ""}:
            return None

        title = text_of(card.css_first(cfg["title"])) if cfg.get("title") else ""
        price = parse_price(text_of(card.css_first(cfg["price"]))) if cfg.get("price") else None
        addr  = text_of(card.css_first(cfg["address"])) if cfg.get("address") else ""
        desc  = text_of(card.css_first(cfg.get("description", ""))) if cfg.get("description") else ""

        street, suburb, city, province = parse_address(addr)

        beds = parse_bedrooms(title + " " + desc)
        if beds is None and cfg.get("beds"):
            beds = first_int(text_of(card.css_first(cfg["beds"])))
        baths = parse_bathrooms(title + " " + desc)
        if baths is None and cfg.get("baths"):
            baths = first_int(text_of(card.css_first(cfg["baths"])))
        land  = parse_price(text_of(card.css_first(cfg["land"])))     if cfg.get("land")     else None
        bldg  = parse_price(text_of(card.css_first(cfg["building"]))) if cfg.get("building") else None

        blob = " ".join(filter(None, [title, addr, desc]))
        allot, sect = parse_allotment_section(blob)
        portion = parse_portion(blob)

        cls, subtype = infer_subtype(title, desc, cfg.get("class_hint"))
        cls = cls or "residential"
        subtype = subtype or (title.split()[0] if title else None)

        return {
            "source_listing_id": source_listing_id,
            "source_url": source_url,
            "purpose": purpose,
            "price": price,
            "rent_period": "monthly" if purpose == "rent" else None,
            "property_class": cls,
            "property_subtype": subtype,
            "allotment_number": allot,
            "section_number": sect,
            "portion_number": portion,
            "street": street, "suburb": suburb,
            "city": city or cfg.get("default_city"),
            "province": province or cfg.get("default_province"),
            "bedrooms": beds, "bathrooms": baths,
            "land_area_m2": land, "building_area_m2": bldg,
            "raw_fields": {"title": title, "address": addr, "description": desc},
        }

    def _parse_page(self, html: Optional[str], cfg: dict, purpose: str,
                    base_url: str) -> list[dict]:
        if not html or not _HAVE_SELECTOLAX:
            return []
        rows: list[dict] = []
        tree = HTMLParser(html)
        for card in tree.css(cfg["card"]):
            row = self._parse_card(card, cfg, purpose, base_url)
            if row:
                rows.append(row)
        return rows

    async def iter_listings(self) -> AsyncIterator[dict]:
        cfg = self._config()
        base = self._base_url()
        headers = {"User-Agent": cfg.get("user_agent",
                                          "TREL-Aggregator/1.0 (+https://trel.com.pg)")}
        max_pages = int(cfg.get("max_pages_per_purpose", 3))

        seen_ids: set[str] = set()

        async with httpx.AsyncClient(timeout=20.0, headers=headers,
                                     follow_redirects=True) as client:
            for path in cfg.get("search_paths", []):
                # Purpose inference: caller can set explicit `search_purposes`
                # aligned to `search_paths` (SRE mixes both on one page); we
                # otherwise infer from the URL fragment.
                purpose = cfg.get("purpose_by_path", {}).get(path)
                if not purpose:
                    purpose = "rent" if "rent" in path.lower() else "sale"
                for page in range(1, max_pages + 1):
                    url = self._pagination_url(cfg, path, page)
                    html = await self._fetch(client, url)
                    if html is None:
                        break
                    rows = self._parse_page(html, cfg, purpose, base)
                    if not rows:
                        break
                    fresh = 0
                    for r in rows:
                        sid = r.get("source_listing_id")
                        if sid in seen_ids:
                            continue
                        seen_ids.add(sid)
                        fresh += 1
                        yield r
                    if fresh == 0:
                        # No new IDs on this page → likely paginating past the
                        # last real page; abort to stay polite to the source.
                        break
