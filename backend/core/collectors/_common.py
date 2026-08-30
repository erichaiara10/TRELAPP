"""Shared building blocks for PNG real-estate HTML collectors.

Every collector inherits `HttpListingCollector`; site-specific files just
declare CSS selectors + optional detail-page selectors. The card grid on a
category page is the initial observation; the collector then follows the
verified detail URL to enrich the record.

Contract with the RunContext (`core.runs.RunContext`)
-----------------------------------------------------
* The collector accepts a RunContext via `iter_listings(run=…)` and calls
  `run.record_diag(...)` at every meaningful checkpoint (page visited,
  card seen/accepted/rejected, detail attempted, pagination stopped).
* If `run` is None (unit-test / discovery-preview mode) diagnostics are
  simply dropped — no crash, no state.

No path guessing anywhere
-------------------------
* Listing category URLs come from `MarketSource.listing_pages` (populated
  by live Discover Pages) — used verbatim.
* Pagination discovers real "Next" mechanisms: `<link rel=next>`,
  `<a rel=next>`, then live "Next" controls, then an explicit
  `parser_config.next_page_selector`. NO `?page=N` fallback.
* Detail URLs are chosen with `_identify_detail_url` (screens for same-
  host, non-nav, deeper-than-category, unique-tail). No first-anchor
  fallback.

Rejection contract (external Market Evidence)
---------------------------------------------
A card is accepted iff BOTH:
* identity → detail URL OR stable source_listing_id (via `_identify_detail_url`)
* numeric sale/rent price extractable from the card

Rejection reasons emitted:
* `no_url_in_card`      — could not identify a detail URL from the card
* `no_numeric_price`    — POA / EOI / Tender / Contact Agent / blank price
* `duplicate_source_id` — same source_listing_id already emitted this run
* `detail_fetch_failed` — card kept, detail enrichment failed (soft)
"""
from __future__ import annotations

import asyncio
import logging
import random
import re
from typing import AsyncIterator, Iterable, Optional
from urllib.parse import urljoin, urlparse

import httpx

from core.collectors import CollectorBase

logger = logging.getLogger(__name__)

try:
    from selectolax.parser import HTMLParser
    _HAVE_SELECTOLAX = True
except ImportError:                                                        # pragma: no cover
    _HAVE_SELECTOLAX = False


# ---------------------------------------------------------------------
# Regex primitives
# ---------------------------------------------------------------------
_NUM_RE = re.compile(r"(\d{1,3}(?:[,\s]\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)")
_INT_RE = re.compile(r"\d+")

# Explicit "no numeric price" markers — case-insensitive match aborts price parse.
_POA_MARKERS = re.compile(
    r"\b(?:poa|price on application|price on request|eoi|"
    r"expressions? of interest|tender|contact agent|contact us|call us|"
    r"enquire|enquiry|by negotiation|neg\.?|negotiable)\b",
    re.IGNORECASE,
)

# Anchor text/URL blacklist for detail-URL screening. Extends discovery.
_NAV_KEYWORDS = [
    "about", "contact", "career", "job", "blog", "news", "team",
    "login", "sign in", "sign-in", "signup", "sign-up", "register",
    "policy", "terms", "privacy", "cookie", "disclaimer", "faq",
    "help", "support", "sitemap", "franchise", "our office", "office",
    "instagram", "facebook", "twitter", "linkedin", "youtube",
    "whatsapp", "tel:", "mailto:", "share", "print",
    "search", "filter", "sort", "compare", "favourite", "favorite", "wishlist",
    "next page", "prev", "previous", "pagination", "page ",
    "agent", "agents", "listing agent", "meet the team",
]

# "Allotment X Section Y" (and permutations)
_ALLOT_RE = re.compile(
    r"(?:allotment|allot|alloc|lot)[\s._-]*(\d+[A-Za-z]?)"
    r"[\s,._/-]+(?:section|sec)[\s._-]*(\d+[A-Za-z]?)",
    re.IGNORECASE,
)
_SECT_ALLOT_RE = re.compile(
    r"(?:section|sec)[\s._-]*(\d+[A-Za-z]?)"
    r"[\s,._/-]+(?:allotment|allot|alloc|lot)[\s._-]*(\d+[A-Za-z]?)",
    re.IGNORECASE,
)
_PORTION_RE = re.compile(r"portion[\s._-]*(\d+[A-Za-z]?)", re.IGNORECASE)

_BEDS_RE = re.compile(r"(\d+)\s*(?:br|bd|bed|bedroom)", re.IGNORECASE)
_BATHS_RE = re.compile(r"(\d+)\s*(?:ba|bth|bath|bathroom)", re.IGNORECASE)
_AREA_RE = re.compile(
    r"(\d[\d,]*(?:\.\d+)?)\s*(?:m(?:2|²)|sq\.?\s*m(?:et(?:re|er)s?)?|sqm)\b",
    re.IGNORECASE,
)
_RENT_PERIODS = (
    (re.compile(r"\b(?:per|a|each|/)\s*(?:week|wk)\b|\bweekly\b", re.I), "weekly"),
    (re.compile(r"\b(?:per|a|each|/)\s*(?:fortnight|fn)\b|\bfortnightly\b", re.I), "fortnightly"),
    (re.compile(r"\b(?:per|a|each|/)\s*(?:day|night)\b|\b(?:daily|nightly)\b", re.I), "daily"),
    (re.compile(r"\b(?:per|a|each|/)\s*(?:month|mth|mo)\b|\bmonthly\b|\bp\.?c\.?m\.?\b", re.I), "monthly"),
    (re.compile(r"\b(?:per|a|each|/)\s*(?:year|annum|yr)\b|\bannual(?:ly)?\b|\bp\.?a\.?\b", re.I), "annual"),
)

_SUBTYPE_HINTS = [
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


# =====================================================================
# Text extractors (public — reused by discovery.py + tests)
# =====================================================================
def parse_price(text: Optional[str]) -> Optional[float]:
    """Numeric extractor. Returns None for POA / EOI / Tender / blank.
    FROM/RANGE strings ("From K450,000", "K450k–K550k") take the first
    numeric anchor."""
    if not text:
        return None
    if _POA_MARKERS.search(text):
        return None
    cleaned = text.replace("PGK", "").replace("K ", " ")
    # "450k"/"450K" shorthand → 450000
    def _shorthand(m: re.Match) -> str:
        n = float(m.group(1).replace(",", ""))
        return str(int(n * 1000))
    cleaned = re.sub(r"(\d+(?:\.\d+)?)\s*[kK](?![a-zA-Z])", _shorthand, cleaned)
    m = _NUM_RE.search(cleaned)
    if not m:
        return None
    try:
        val = float(m.group(1).replace(",", "").replace(" ", ""))
    except ValueError:
        return None
    # Below-1 values are almost always false positives (bathrooms, half-baths,
    # etc.); real PNG prices start at PGK 300+.
    return val if val >= 100 else None


def first_int(text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    m = _INT_RE.search(text)
    return int(m.group(0)) if m else None


def parse_allotment_section(text: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    if not text:
        return None, None
    m = _ALLOT_RE.search(text)
    if m:
        return m.group(1), m.group(2)
    m = _SECT_ALLOT_RE.search(text)
    if m:
        return m.group(2), m.group(1)
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


def parse_area(text: Optional[str]) -> Optional[float]:
    """Extract an explicitly-labelled square-metre area, never a bare number."""
    if not text:
        return None
    m = _AREA_RE.search(text)
    return float(m.group(1).replace(",", "")) if m else None


def parse_rent_period(text: Optional[str]) -> Optional[str]:
    """Return only a cadence stated by the source; do not invent a default."""
    for pattern, period in _RENT_PERIODS:
        if text and pattern.search(text):
            return period
    return None


def parse_address(addr: Optional[str]) -> tuple[Optional[str], Optional[str],
                                                Optional[str], Optional[str]]:
    if not addr:
        return None, None, None, None
    parts = [p.strip() for p in addr.split(",") if p.strip()]
    return (parts[0] if len(parts) >= 1 else None,
            parts[1] if len(parts) >= 2 else None,
            parts[2] if len(parts) >= 3 else None,
            parts[3] if len(parts) >= 4 else None)


def parse_location(addr: Optional[str], *, default_city: Optional[str] = None,
                   default_province: Optional[str] = None) -> dict:
    """Parse PNG listing locations without treating every first token as a street.

    Four-part addresses retain the established street/suburb/city/province mapping.
    Shorter source strings are aligned from the right when they explicitly end in
    the configured city/province. A leading non-address component is preserved as
    the building name (for example ``Pacific View Apartments, Ela Beach, ...``).
    """
    parts = [p.strip() for p in (addr or "").split(",") if p.strip()]
    result = {"building_name": None, "street": None, "suburb": None,
              "local_area": None, "city": default_city,
              "province": default_province}
    if not parts:
        return result
    if default_province and parts[-1].casefold() == default_province.casefold():
        result["province"] = parts.pop()
    if default_city and parts and parts[-1].casefold() == default_city.casefold():
        result["city"] = parts.pop()
    streetish = re.compile(r"(?:\d|\b(?:road|rd|street|st|drive|dr|avenue|ave|close|crescent|lane|way|highway|hwy)\b)", re.I)
    if len(parts) >= 2 and not streetish.search(parts[0]):
        result["building_name"] = parts.pop(0)
    if len(parts) >= 2:
        result["street"], result["suburb"] = parts[0], parts[1]
        if len(parts) > 2:
            result["local_area"] = parts[2]
    elif len(parts) == 1:
        if streetish.search(parts[0]):
            result["street"] = parts[0]
        else:
            result["suburb"] = parts[0]
    return result


def infer_subtype(*texts: str) -> tuple[Optional[str], Optional[str]]:
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


def _selector_text(root, selector: str | None) -> str:
    """Return the first non-empty selector match without allowing a bad
    source profile to abort an entire collection run."""
    if not root or not selector:
        return ""
    try:
        for node in root.css(selector):
            value = text_of(node)
            if value:
                return value
    except Exception:
        return ""
    return ""


def smart_price_text(root, selector: str | None = None) -> str:
    """Extract a price using configured selectors first, then semantic
    fallbacks. The fallback is deterministic and deliberately PNG-currency
    aware; it is used for discovery validation as well as collection."""
    configured = _selector_text(root, selector)
    if configured:
        return configured
    semantic = _selector_text(
        root,
        ".s3-pr, .l3-price, [itemprop='price'], [data-price], "
        ".price, [class*='price'], [class$='-pr'], [class$='_pr']",
    )
    if semantic:
        return semantic
    try:
        for node in root.css("strong, b, span, div, p"):
            value = text_of(node)
            if len(value) <= 80 and re.search(
                r"(?:\\bPGK\\b|\\bK\\s*)\\d[\\d,]*(?:\\.\\d+)?",
                value, re.IGNORECASE,
            ):
                return value
            if len(value) <= 80 and _POA_MARKERS.search(value):
                return value
    except Exception:
        pass
    return ""


def smart_field_text(root, selector: str | None, field: str) -> str:
    configured = _selector_text(root, selector)
    if configured:
        return configured
    fallbacks = {
        "title": ".s3-hl, [itemprop='name'], h1, h2, h3",
        "address": ".s3-ad, .l3-addr, .l3-sub, [itemprop='address'], "
                   "[class*='address'], [class*='location']",
        "description": ".l3-desc, [itemprop='description'], "
                       "[class*='description'], [class*='details']",
    }
    return _selector_text(root, fallbacks.get(field))


def price_status(text: str | None) -> str:
    if text and _POA_MARKERS.search(text):
        return "UNPRICED"
    return "PRICED" if parse_price(text) is not None else "MISSING"


def _page_key(url: str) -> str:
    parsed = urlparse(url)
    path = re.sub(r"/+$", "", parsed.path or "/") or "/"
    query = "&".join(sorted(filter(None, parsed.query.split("&"))))
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{path}" + (
        f"?{query}" if query else ""
    )



# =====================================================================
# Detail-URL identification (shared by collector + discovery)
# =====================================================================
def _norm_host(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().lstrip("www.")
    except Exception:
        return ""


def _looks_navish(text: str, href: str) -> bool:
    blob = f"{text.lower()} {href.lower()}"
    return any(kw in blob for kw in _NAV_KEYWORDS)


def _path_parts(url: str) -> list[str]:
    return [p for p in urlparse(url).path.split("/") if p]


def _identify_detail_url(card_or_anchors, base_url: str,
                         category_page_url: Optional[str] = None) -> Optional[str]:
    """Pick the most-likely detail URL for a listing card. Screens candidates:

    * same host as base_url
    * not equal to the category page
    * not a nav/social/agent/pagination link
    * path extends BENEATH the category page path (has one or more extra
      non-empty segments), OR contains a numeric-ID tail
    * unique-looking tail (has letters+digits or a hyphenated slug)

    Accepts either an HTMLParser node (a card) OR an iterable of anchor
    nodes. Returns the resolved absolute URL, or None if nothing qualifies.
    """
    if card_or_anchors is None:
        return None
    if hasattr(card_or_anchors, "css"):
        anchors = card_or_anchors.css("a[href]")
    else:
        anchors = list(card_or_anchors)
    if not anchors:
        return None

    base_host = _norm_host(base_url)
    cat_parts = _path_parts(category_page_url) if category_page_url else []
    cat_url_clean = (category_page_url or "").rstrip("/").split("#", 1)[0].split("?", 1)[0]

    scored: list[tuple[int, str]] = []
    for a in anchors:
        href = (a.attributes.get("href") or "").strip()
        if not href or href.startswith("#") or href.lower().startswith(("javascript:", "mailto:", "tel:")):
            continue
        abs_url = urljoin(base_url, href)
        clean = abs_url.rstrip("/").split("#", 1)[0].split("?", 1)[0]
        if clean == cat_url_clean:
            continue
        if _norm_host(abs_url) != base_host:
            continue
        text = (a.text(strip=True) or "").strip()
        if _looks_navish(text, abs_url):
            continue
        parts = _path_parts(abs_url)
        if not parts:
            continue
        tail = parts[-1]
        # Score candidates — highest score wins.
        score = 0
        # Below category path
        if cat_parts and parts[:len(cat_parts)] == cat_parts and len(parts) > len(cat_parts):
            score += 4
        # Extra depth vs. category
        if cat_parts and len(parts) > len(cat_parts):
            score += 1
        # Numeric-ID somewhere in the tail (e.g. /property/12345/foo, /buy/12345-house)
        if _INT_RE.search(tail):
            score += 3
        # Hyphenated slug (multi-word)
        if "-" in tail and len(tail) > 5:
            score += 2
        # Has text (likely a title anchor rather than an icon-only link)
        if text and len(text) > 8:
            score += 1
        # Bonus for common canonical patterns
        for hint in ("/property/", "/listing/", "/properties/", "/listings/",
                     "/ad/", "/homes/", "/houses/", "/estate/", "/details/"):
            if hint in abs_url.lower():
                score += 2
                break
        if score <= 0:
            continue
        scored.append((score, abs_url))

    if not scored:
        return None
    scored.sort(key=lambda t: -t[0])
    return scored[0][1]


# =====================================================================
# Pagination discovery (no ?page=N fallback)
# =====================================================================
def _find_next_page_url(html: str, current_url: str,
                        cfg: dict) -> Optional[str]:
    """Discover the actual "Next" URL exposed by the source. Precedence:

    1. `<link rel="next">` in `<head>`
    2. `<a rel="next">` anywhere in body
    3. Live "Next" controls — `.next a`, `[aria-label*=next i]`,
       anchors with visible text "Next" / "→" / "»" / "›"
    4. Source-specific `parser_config.next_page_selector` (CSS selector
       resolving to an `<a href>`)

    Returns the absolute URL or None. NEVER guesses `?page=N`.
    """
    if not html or not _HAVE_SELECTOLAX:
        return None
    tree = HTMLParser(html)
    base = current_url

    # 1 + 2
    for sel in ("link[rel='next'][href]", "a[rel='next'][href]"):
        n = tree.css_first(sel)
        href = attr_of(n, "href")
        if href:
            return urljoin(base, href)

    # 3 — live "Next" controls
    live_selectors = [
        "nav[aria-label*='pagination' i] a[rel='next']",
        "[aria-label*='next' i][href]",
        ".pagination a[rel='next']",
        ".pagination .next a",
        "a.next",
        "li.next a",
    ]
    for sel in live_selectors:
        n = tree.css_first(sel)
        href = attr_of(n, "href")
        if href:
            return urljoin(base, href)

    # 3b — anchor whose visible text is one of Next / › / » / →
    for a in tree.css("a[href]"):
        t = (a.text(strip=True) or "").strip().lower()
        if t in ("next", "next »", "next ›", "next >", "›", "»", "→", ">"):
            href = a.attributes.get("href") or ""
            if href and not href.startswith("#"):
                return urljoin(base, href)

    # 4 — source-specific
    custom = cfg.get("next_page_selector")
    if custom:
        n = tree.css_first(custom)
        href = attr_of(n, "href")
        if href:
            return urljoin(base, href)

    return None


# =====================================================================
# HTTP fetcher with Retry-After honouring + exponential backoff
# =====================================================================
async def _fetch_with_retries(client: httpx.AsyncClient, url: str,
                              *, max_retries: int = 3,
                              base_delay_ms: int = 2000) -> tuple[Optional[str], int]:
    """Return `(html, status)`. On 429/503 honours `Retry-After` up to
    `max_retries` times with exponential backoff, then gives up."""
    delay_ms = base_delay_ms
    for attempt in range(max_retries + 1):
        try:
            r = await client.get(url)
            if r.status_code in (429, 503) and attempt < max_retries:
                ra = r.headers.get("Retry-After")
                wait = delay_ms
                if ra and ra.isdigit():
                    wait = int(ra) * 1000
                await asyncio.sleep(wait / 1000.0)
                delay_ms *= 2
                continue
            return r.text if r.status_code < 400 else None, r.status_code
        except Exception as e:                                          # noqa: BLE001
            logger.info(f"fetch {url}: {type(e).__name__}: {e}")
            if attempt < max_retries:
                await asyncio.sleep(delay_ms / 1000.0)
                delay_ms *= 2
                continue
            return None, 0
    return None, 0


# =====================================================================
# Base HTTP + HTML collector
# =====================================================================


def _canonical_listing_pages(pages: list[dict]) -> list[dict]:
    """Return the smallest non-overlapping set of confirmed starting pages.

    New discovery profiles explicitly mark canonical pages. Legacy profiles
    are collapsed to the shallowest page per sale/rent purpose so old
    subcategory/location URLs cannot multiply the same inventory.
    """
    pages = [p for p in pages if isinstance(p, dict) and p.get("listing_url")]
    if not pages:
        return []
    explicit = [
        p for p in pages
        if p.get("canonical") is True and not p.get("covered_by")
    ]
    if explicit:
        return explicit
    selected: list[dict] = []
    for purpose in ("sale", "rent"):
        family = [
            p for p in pages
            if (p.get("purpose") or (
                "rent" if "rent" in str(p.get("listing_url", "")).lower() else "sale"
            )) == purpose
        ]
        if family:
            selected.append(min(
                family,
                key=lambda p: (
                    len(_path_parts(str(p.get("listing_url")))),
                    len(str(p.get("listing_url"))),
                ),
            ))
    projects = [
        p for p in pages
        if str(p.get("category") or "").lower() in {"projects", "new_developments"}
        and p not in selected
    ]
    return selected + projects


class HttpListingCollector(CollectorBase):
    """Contract every network-backed collector inherits. Subclasses set
    `DEFAULT_CONFIG` (see the concrete collector files)."""

    requires_network = True
    DEFAULT_CONFIG: dict = {}
    # Per-source overrides live on MarketSource.parser_config. Every key
    # in DEFAULT_CONFIG is override-able. Keys with special meaning:
    #   next_page_selector      — CSS selector for a next-page <a>
    #   crawl_details           — bool, default True
    #   detail_selectors        — dict of field → CSS selector for the
    #                             detail page
    #   detail_concurrency      — int, default 2
    #   request_delay_ms        — int, default 500 (per-request jitter)
    #   max_pages_safety_ceiling — int, default 50 (runaway guard, not
    #                              a "stop here" target)

    def _config(self) -> dict:
        cfg = dict(self.DEFAULT_CONFIG)
        cfg.update(self.source.get("parser_config") or {})
        cfg.setdefault("crawl_details", True)
        cfg.setdefault("detail_concurrency", 2)
        cfg.setdefault("request_delay_ms", 500)
        cfg.setdefault("max_pages_safety_ceiling", 50)
        return cfg

    def _base_url(self) -> str:
        return (self.source.get("base_url")
                or self.DEFAULT_CONFIG.get("base_url", "")).rstrip("/")

    async def iter_listings(self, run=None) -> AsyncIterator[dict]:
        cfg = self._config()
        base = self._base_url()
        headers = {"User-Agent": cfg.get("user_agent",
                   "TREL-Aggregator/1.0 (+https://trel.com.pg)")}

        listing_pages = _canonical_listing_pages(self.source.get("listing_pages") or [])
        if not listing_pages:
            logger.warning(f"{self.key} source '{self.source.get('name')}' has no "
                           f"listing_pages — run Discover Pages first")
            _record(run, "no_listing_pages_configured")
            return

        seen_ids: set[str] = set()
        detail_sem = asyncio.Semaphore(int(cfg["detail_concurrency"]))
        delay_ms = int(cfg["request_delay_ms"])

        async with httpx.AsyncClient(timeout=15.0, headers=headers,
                                     follow_redirects=True) as client:
            for page_entry in listing_pages:
                listing_url = (page_entry or {}).get("listing_url")
                if not listing_url:
                    continue
                purpose = (page_entry.get("purpose")
                           or self._infer_purpose(page_entry, listing_url))
                async for row in self._walk_category(
                        client, listing_url, cfg, purpose, base,
                        seen_ids, detail_sem, delay_ms, run):
                    yield row

    def _infer_purpose(self, page_entry: dict, url: str) -> str:
        blob = " ".join([
            (page_entry.get("category") or ""),
            (page_entry.get("category_label") or ""), url,
        ]).lower()
        if any(w in blob for w in ("rent", "lease", "leasing", "rental")):
            return "rent"
        return "sale"

    async def _walk_category(self, client, listing_url: str, cfg: dict,
                             purpose: str, base: str, seen_ids: set[str],
                             detail_sem: asyncio.Semaphore, delay_ms: int,
                             run) -> AsyncIterator[dict]:
        """Walk one confirmed category page + its Next pages."""
        current_url: Optional[str] = listing_url
        page_no = 0
        ceiling = int(cfg["max_pages_safety_ceiling"])
        visited_pages: set[str] = set()
        while current_url and page_no < ceiling:
            _check_cancelled(run)
            current_key = _page_key(current_url)
            if current_key in visited_pages:
                _record_pagination_end(run, "pagination_cycle_detected")
                break
            visited_pages.add(current_key)
            page_no += 1
            _record(run, "page_fetch_started", url=current_url)
            html, status = await _fetch_with_retries(client, current_url)
            _record(run, "page_fetched", url=current_url, status=status)
            if not html:
                _record(run, "page_fetch_failed", url=current_url, status=status)
                _record_page(run, current_url, cards_seen=0,
                             cards_accepted=0, cards_rejected=0, final=True)
                break

            cards = self._select_cards(html, cfg)
            accepted = 0; rejected = 0
            parsed_rows = []
            for card in cards:
                _check_cancelled(run)
                _record(run, "card_seen")
                row, reject_reason = self._parse_card(
                    card, cfg, purpose, base, category_page_url=current_url,
                )
                if reject_reason:
                    rejected += 1
                    _record(run, reject_reason)
                    continue
                sid = row.get("source_listing_id")
                if sid and sid in seen_ids:
                    rejected += 1
                    _record(run, "duplicate_source_id_within_run")
                    continue
                if sid:
                    seen_ids.add(sid)

                parsed_rows.append(row)

            async def enrich_row(row):
                # Detail requests are independent, so execute them under the
                # configured semaphore rather than serially stalling a run.
                if cfg["crawl_details"] and row.get("source_url"):
                    _record(
                        run, "detail_page_attempted",
                        inc="detail_pages_attempted", url=row["source_url"],
                    )
                    enriched, ok = await self._enrich(
                        client, row["source_url"], cfg,
                        detail_sem, delay_ms, run)
                    if ok:
                        _record(run, "detail_page_succeeded",
                                inc="detail_pages_succeeded")
                        row = {**row, **{k: v for k, v in enriched.items()
                                          if v is not None and v != ""}}
                    else:
                        _record(run, "detail_fetch_failed",
                                inc="detail_pages_failed")
                return row

            enriched_rows = await asyncio.gather(*(enrich_row(row) for row in parsed_rows))
            for row in enriched_rows:
                if row.get("price") is None and row.get("price_status") != "UNPRICED":
                    rejected += 1
                    _record(run, "no_numeric_price")
                    continue
                accepted += 1
                _record(run, "card_accepted")
                yield row

            _record_page(run, current_url, cards_seen=len(cards),
                         cards_accepted=accepted, cards_rejected=rejected,
                         final=True)

            if accepted == 0 and rejected == 0 and cards:
                # Cards existed but every one was scored 0 by URL screener —
                # extremely unlikely, but stop pagination to avoid runaway.
                _record_pagination_end(run, "no_extractable_cards")
                break

            next_url = _find_next_page_url(html, current_url, cfg)
            if next_url and _page_key(next_url) in visited_pages:
                _record_pagination_end(run, "pagination_cycle_detected")
                break
            if not next_url or _page_key(next_url) == _page_key(current_url):
                _record_pagination_end(
                    run, "no_next_link" if not next_url else "next_equals_current")
                break

            # Jitter between page fetches (politeness)
            await asyncio.sleep((delay_ms + random.randint(0, delay_ms)) / 1000.0)
            current_url = next_url

        if page_no >= ceiling:
            _record_pagination_end(run, "safety_ceiling_hit")

    def _select_cards(self, html: str, cfg: dict) -> list:
        if not _HAVE_SELECTOLAX:
            return []
        tree = HTMLParser(html)
        return tree.css(cfg.get("card") or "article, .listing, .property")

    def _parse_card(self, card, cfg: dict, purpose: str, base_url: str,
                    category_page_url: Optional[str] = None
                    ) -> tuple[Optional[dict], Optional[str]]:
        """Extract one listing tile. Returns `(row, None)` on accept, or
        `(None, reason)` on reject. Missing beds/baths/area do NOT reject —
        only URL identity failure or non-numeric price."""
        # Detail URL — new stricter identifier (used to be first-anchor fallback).
        source_url = _identify_detail_url(card, base_url, category_page_url)
        if not source_url:
            return None, "no_url_in_card"
        source_listing_id = _path_parts(source_url)[-1] or source_url

        title = smart_field_text(card, cfg.get("title"), "title")
        price_text = smart_price_text(card, cfg.get("price"))
        price = parse_price(price_text)

        addr = smart_field_text(card, cfg.get("address"), "address")
        desc = smart_field_text(card, cfg.get("description"), "description")
        location = parse_location(addr, default_city=cfg.get("default_city"),
                                  default_province=cfg.get("default_province"))

        beds = parse_bedrooms(title + " " + desc)
        if beds is None and cfg.get("beds"):
            beds = first_int(text_of(card.css_first(cfg["beds"])))
        baths = parse_bathrooms(title + " " + desc)
        if baths is None and cfg.get("baths"):
            baths = first_int(text_of(card.css_first(cfg["baths"])))
        land = parse_area(text_of(card.css_first(cfg["land"])))     if cfg.get("land")     else None
        bldg = parse_area(text_of(card.css_first(cfg["building"]))) if cfg.get("building") else None

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
            "price_status": price_status(price_text),
            "rent_period": parse_rent_period(price_text) if purpose == "rent" else None,
            "property_class": cls,
            "property_subtype": subtype,
            "allotment_number": allot,
            "section_number": sect,
            "portion_number": portion,
            **location,
            "bedrooms": beds, "bathrooms": baths,
            "land_area_m2": land, "building_area_m2": bldg,
            "raw_fields": {"title": title, "address": addr, "description": desc,
                           "price_raw": price_text},
        }, None

    async def _enrich(self, client: httpx.AsyncClient, url: str, cfg: dict,
                      sem: asyncio.Semaphore, delay_ms: int, run
                      ) -> tuple[dict, bool]:
        """Fetch the detail page and extract configured fields. Returns
        (enrichment_dict, ok_flag). Never raises."""
        ds = cfg.get("detail_selectors") or {}
        if not ds:
            return {}, True                # collector disabled detail crawl
        async with sem:
            await asyncio.sleep((delay_ms + random.randint(0, delay_ms)) / 1000.0)
            html, status = await _fetch_with_retries(client, url,
                                                     max_retries=2, base_delay_ms=1500)
        if not html:
            return {}, False
        if not _HAVE_SELECTOLAX:                                            # pragma: no cover
            return {}, False
        tree = HTMLParser(html)
        out: dict = {}
        text_map = {
            "title": ("title", text_of),
            "description": ("description", text_of),
            "address": ("address", text_of),
        }
        for k, (out_key, fn) in text_map.items():
            sel = ds.get(k)
            if sel:
                val = fn(tree.css_first(sel))
                if val:
                    out[out_key] = val
        detail_price_text = smart_price_text(tree, ds.get("price"))
        if detail_price_text:
            v = parse_price(detail_price_text)
            if v is not None:
                out["price"] = v
                out["price_status"] = "PRICED"
            elif _POA_MARKERS.search(detail_price_text):
                out["price_status"] = "UNPRICED"
        for k in ("bedrooms", "bathrooms"):
            sel = ds.get(k)
            if sel:
                v = first_int(text_of(tree.css_first(sel)))
                if v is not None:
                    out[k] = v
        if ds.get("land_area"):
            v = parse_area(text_of(tree.css_first(ds["land_area"])))
            if v is not None:
                out["land_area_m2"] = v
        if ds.get("building_area"):
            v = parse_area(text_of(tree.css_first(ds["building_area"])))
            if v is not None:
                out["building_area_m2"] = v
        # Detail page may also expose Allotment / Section explicitly
        page_text = tree.body.text() if tree.body else ""
        allot, sect = parse_allotment_section(page_text)
        if allot:
            out["allotment_number"] = allot
        if sect:
            out["section_number"] = sect
        portion = parse_portion(page_text)
        if portion:
            out["portion_number"] = portion
        detail_price = detail_price_text
        period = parse_rent_period(detail_price)
        if period:
            out["rent_period"] = period
        detail_address = out.pop("address", "")
        if detail_address:
            out.update({k: v for k, v in parse_location(
                detail_address, default_city=cfg.get("default_city"),
                default_province=cfg.get("default_province")).items() if v})
        detail_title = out.pop("title", "")
        detail_description = out.pop("description", "")
        cls, subtype = infer_subtype(detail_title, detail_description)
        if cls:
            out["property_class"] = cls
        if subtype:
            out["property_subtype"] = subtype
        if out.get("bedrooms") is None:
            out["bedrooms"] = parse_bedrooms(f"{detail_title} {detail_description}")
        if out.get("bathrooms") is None:
            out["bathrooms"] = parse_bathrooms(f"{detail_title} {detail_description}")
        return out, True


# =====================================================================
# Diagnostic helpers — safe when `run` is None
# =====================================================================
def _check_cancelled(run) -> None:
    if run is None:
        return
    fn = getattr(run, "raise_if_cancelled", None)
    if fn:
        fn()


def _record(run, reason: str, *, inc: str | None = None,
             url: str | None = None, status: int | None = None) -> None:
    if run is None:
        return
    fn = getattr(run, "record_diag", None)
    if fn:
        fn(reason, inc=inc, url=url, status=status)


def _record_page(run, url: str, cards_seen: int, cards_accepted: int,
                 cards_rejected: int, final: bool = False) -> None:
    if run is None:
        return
    fn = getattr(run, "record_page", None)
    if fn:
        fn(url, cards_seen, cards_accepted, cards_rejected, final=final)


def _record_pagination_end(run, reason: str) -> None:
    if run is None:
        return
    fn = getattr(run, "record_pagination_end", None)
    if fn:
        fn(reason)
