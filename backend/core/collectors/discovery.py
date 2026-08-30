"""Live listing-page discovery.

Given a real-estate homepage, walk the site's navigation, follow candidate
links to whatever category pages they resolve to, and grade each candidate
by whether the response looks like an actual listings grid.

Zero URL guessing:
* We NEVER build paths from templates (`/property-for-sale`, `/rent/`, …).
* We only follow links that the target site itself has written on its own
  homepage / primary navigation.
* Each candidate's `listing_url` is the final URL after following redirects.
* The `cards_found` grade uses the collector's own card selector so ops see
  exactly what the scraper will see.
"""
from __future__ import annotations

import logging
import re
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx

from core.collectors import get_collector
from core.collectors._common import HttpListingCollector, _identify_detail_url

logger = logging.getLogger(__name__)

try:
    from selectolax.parser import HTMLParser
    _HAVE_SELECTOLAX = True
except ImportError:                                                     # pragma: no cover
    _HAVE_SELECTOLAX = False


# ---------------------------------------------------------------------
# Category keyword → human label. Keywords are matched against link TEXT
# (case-insensitive substring) and the URL path segment; NEVER used to
# construct URLs — only to CLASSIFY the ones the site itself exposes.
# ---------------------------------------------------------------------
CATEGORY_RULES = [
    # order matters — most-specific first
    {"key": "buy_for_sale", "label": "Buy / For Sale",
     "keywords": ["for sale", "for-sale", "properties for sale"],
     "purpose": "sale"},
    {"key": "buy",          "label": "Buy",
     "keywords": ["buy", "buying"],                                     "purpose": "sale"},
    {"key": "rent",         "label": "Rent",
     "keywords": ["for rent", "for-rent", "to rent", "rent",
                  "lease", "for lease", "leasing", "rentals"],
     "purpose": "rent"},
    {"key": "residential",  "label": "Residential",
     "keywords": ["residential"],                                       "purpose": "sale"},
    {"key": "commercial",   "label": "Commercial",
     "keywords": ["commercial", "office", "retail", "warehouse"],
     "purpose": "sale"},
    {"key": "land",         "label": "Land",
     "keywords": ["vacant land", "land for sale", " land ", "/land",
                  "sections", "portions"],                              "purpose": "sale"},
    {"key": "projects",     "label": "Projects / New Developments",
     "keywords": ["projects", "new developments", "off the plan",
                  "off-the-plan"],                                       "purpose": "sale"},
    {"key": "apartments",   "label": "Apartments",
     "keywords": ["apartments", "units"],                               "purpose": "sale"},
    {"key": "houses",       "label": "Houses",
     "keywords": ["houses"],                                            "purpose": "sale"},
]

# Anchors we never want to follow (login/contact/about/etc)
_BLACKLIST_KEYWORDS = [
    "about", "contact", "career", "job", "blog", "news", "team",
    "login", "sign in", "sign-in", "signup", "sign-up", "register",
    "policy", "terms", "privacy", "cookie", "disclaimer", "faq",
    "help", "support", "sitemap", "franchise", "our office",
    "instagram", "facebook", "twitter", "linkedin", "youtube",
    "whatsapp", "tel:", "mailto:",
]

_LISTING_LINK_HINTS_LEGACY_NOTE = (
    # Left as documentation only — replaced by the shared `_identify_detail_url`
    # so the Discover Pages counter and the real scraper always agree on what
    # qualifies as a detail link.
    "moved to core.collectors._common._identify_detail_url"
)


def _classify(text: str, url_path: str) -> Optional[dict]:
    """Return the first matching CATEGORY_RULES entry (or None). We test
    both the visible link text and the URL path so `href="/buy/"` with
    `text="Properties"` still lands on the Buy category."""
    blob = f" {text.lower().strip()} {url_path.lower()} "
    for rule in CATEGORY_RULES:
        for kw in rule["keywords"]:
            if kw in blob:
                return rule
    return None


def _is_blacklisted(text: str, url: str) -> bool:
    blob = f"{text.lower()} {url.lower()}"
    return any(bad in blob for bad in _BLACKLIST_KEYWORDS)


def _same_host(base: str, candidate: str) -> bool:
    try:
        b = urlparse(base).netloc.lower().lstrip("www.")
        c = urlparse(candidate).netloc.lower().lstrip("www.")
        return c == b or c.endswith("." + b) or b.endswith("." + c) or not c
    except Exception:
        return False


def _clean_url(url: str) -> str:
    """Strip fragments; the same category with #x variations is still
    the same page and should be deduped."""
    return url.split("#", 1)[0].rstrip("/")


async def _fetch(client: httpx.AsyncClient, url: str) -> tuple[Optional[str], Optional[str], int]:
    """Fetch `url`, follow redirects. Returns `(final_url, html, status)`.
    On any error returns `(None, None, 0)`."""
    try:
        r = await client.get(url)
        return str(r.url), r.text, r.status_code
    except Exception as e:                                              # noqa: BLE001
        logger.info(f"discover fetch {url}: {e}")
        return None, None, 0


def _extract_candidates(html: str, base_url: str) -> list[dict]:
    """Extract same-site navigation without depending on hard-coded paths."""
    if not _HAVE_SELECTOLAX:
        return []
    tree = HTMLParser(html)
    seen: dict[str, dict] = {}
    for a in tree.css("a[href]"):
        href = (a.attributes.get("href") or "").strip()
        if not href or href.startswith("#") or href.lower().startswith(("javascript:", "mailto:", "tel:")):
            continue
        text = (a.text(strip=True) or "").strip()
        absolute = _clean_url(urljoin(base_url, href))
        if not _same_host(base_url, absolute) or _is_blacklisted(text, absolute):
            continue
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"}:
            continue
        seen.setdefault(absolute, {
            "url": absolute, "text": text,
            "rule": _classify(text, parsed.path),
        })
    return list(seen.values())


def _page_rule(html: str, candidate: dict) -> dict | None:
    """Semantic classification from URL, link text, title and page headings."""
    text = candidate.get("text") or ""
    if _HAVE_SELECTOLAX and html:
        tree = HTMLParser(html)
        signals = []
        for selector in ("title", "h1", "h2", "[aria-label]", "meta[name=description]"):
            for node in tree.css(selector)[:8]:
                signals.append(
                    node.attributes.get("content") or node.attributes.get("aria-label")
                    or node.text(strip=True) or ""
                )
        text = " ".join([text, *signals])
    return candidate.get("rule") or _classify(text, urlparse(candidate["url"]).path)


def _path_depth(url: str) -> int:
    return len([part for part in urlparse(url).path.split("/") if part])


def _looks_traversable(candidate: dict, depth: int) -> bool:
    """Keep the crawl focused while allowing unfamiliar nested site structures."""
    if depth <= 1:
        return True
    blob = f"{candidate.get('text', '')} {urlparse(candidate['url']).path}".lower()
    semantic = (
        "propert", "listing", "real estate", "home", "house", "apartment",
        "land", "commercial", "develop", "sale", "buy", "rent", "lease",
        "search", "location", "residential",
    )
    return candidate.get("rule") is not None or any(word in blob for word in semantic)


def _canonicalise(candidates: list[dict]) -> None:
    """Select one highest-level page per purpose; keep covered subpages visible."""
    verified = [c for c in candidates if c.get("verified_listing_page")]
    for purpose in ("sale", "rent"):
        family = [c for c in verified if c.get("purpose") == purpose]
        if not family:
            continue
        primary = min(
            family,
            key=lambda item: (
                _path_depth(item["listing_url"]),
                -int(item.get("detail_links") or 0),
                -int(item.get("cards_found") or 0),
            ),
        )
        primary["canonical"] = True
        primary["auto_confirm"] = True
        primary["selection_reason"] = "Highest-level verified listing page"
        for item in family:
            if item is primary:
                continue
            if item.get("category") == "projects":
                item["canonical"] = True
                item["auto_confirm"] = True
                item["selection_reason"] = "Distinct new-development inventory"
            else:
                item["canonical"] = False
                item["auto_confirm"] = False
                item["covered_by"] = primary["listing_url"]
                item["selection_reason"] = "Subcategory/location page covered by the canonical page"


def _count_cards(html: str, card_selector: str, base_url: str,
                 category_url: str) -> tuple[int, int]:
    if not html or not _HAVE_SELECTOLAX:
        return 0, 0
    tree = HTMLParser(html)
    cards = tree.css(card_selector or "article, .listing, .property")
    detail_links = sum(
        1 for card in cards
        if _identify_detail_url(card, base_url, category_url)
    )
    return len(cards), detail_links


async def discover_listing_pages(base_url: str, collector_key: str,
                                   parser_config: dict | None = None) -> dict:
    """Intelligently traverse the site's own links and verify listing grids.

    This is deliberately a hybrid: semantic signals find unfamiliar nested
    paths; repeated cards and detail links provide deterministic verification.
    """
    if not base_url or not base_url.startswith("http"):
        return {"ok": False, "error": "Valid base URL required", "candidates": []}
    if not _HAVE_SELECTOLAX:
        return {"ok": False, "error": "selectolax not installed", "candidates": []}
    Coll = get_collector(collector_key)
    if not Coll or not issubclass(Coll, HttpListingCollector):
        return {"ok": False, "error": f"Collector '{collector_key}' is not an HTTP scraper", "candidates": []}

    import asyncio
    cfg = dict(Coll.DEFAULT_CONFIG)
    cfg.update(parser_config or {})
    card_selector = cfg.get("card") or "article, .listing, .property"
    scan_limit = max(20, min(int(cfg.get("discovery_page_limit", 60)), 200))
    max_depth = max(2, min(int(cfg.get("discovery_depth", 4)), 6))
    headers = {"User-Agent": cfg.get("user_agent", "TREL-Aggregator/1.0 (+https://trel.com.pg)")}

    queue: list[tuple[str, str, int]] = [(base_url, "Website home", 0)]
    queued = {_clean_url(base_url)}
    visited: set[str] = set()
    candidates: list[dict] = []
    errors: list[dict] = []
    resolved_home = base_url
    home_status = 0

    async with httpx.AsyncClient(timeout=10.0, headers=headers, follow_redirects=True) as client:
        while queue and len(visited) < scan_limit:
            url, link_text, depth = queue.pop(0)
            clean = _clean_url(url)
            if clean in visited:
                continue
            visited.add(clean)
            final_url, html, status = await _fetch(client, clean)
            if depth == 0:
                resolved_home, home_status = final_url or clean, status
            if not html or status >= 400:
                errors.append({"url": clean, "status": status, "reason": "unreachable"})
                continue

            current = {"url": _clean_url(final_url or clean), "text": link_text, "rule": None}
            rule = _page_rule(html, current)
            cards_found, detail_links = _count_cards(
                html, card_selector, resolved_home or base_url, current["url"]
            )
            verified = cards_found > 0 and detail_links > 0
            if verified or rule:
                effective = rule or {
                    "key": "unknown", "label": "Property Listings",
                    "purpose": "rent" if "rent" in (link_text + current["url"]).lower() else "sale",
                }
                confidence = min(99, 45 + min(cards_found, 20) * 2 + min(detail_links, 20))
                candidates.append({
                    "category": effective["key"], "category_label": effective["label"],
                    "purpose": effective["purpose"], "link_text": link_text,
                    "listing_url": current["url"], "status": status,
                    "cards_found": cards_found, "detail_links": detail_links,
                    "accessible": True, "verified_listing_page": verified,
                    "confidence": confidence if verified else min(confidence, 55),
                    "auto_confirm": False, "canonical": False,
                })

            if depth >= max_depth:
                continue
            links = _extract_candidates(html, current["url"])
            links.sort(key=lambda item: (
                -int(item.get("rule") is not None), _path_depth(item["url"])
            ))
            for item in links:
                item_url = _clean_url(item["url"])
                if item_url in visited or item_url in queued:
                    continue
                if not _looks_traversable(item, depth + 1):
                    continue
                queued.add(item_url)
                queue.append((item_url, item.get("text") or "", depth + 1))
            await asyncio.sleep(0)

    # Resolve redirects/duplicate links before choosing canonical pages.
    unique: dict[str, dict] = {}
    for item in candidates:
        prior = unique.get(item["listing_url"])
        if not prior or (item["detail_links"], item["cards_found"]) > (prior["detail_links"], prior["cards_found"]):
            unique[item["listing_url"]] = item
    candidates = list(unique.values())
    _canonicalise(candidates)
    candidates.sort(key=lambda item: (
        -int(item.get("auto_confirm", False)),
        -int(item.get("verified_listing_page", False)),
        -int(item.get("confidence", 0)),
        _path_depth(item["listing_url"]),
    ))
    return {
        "ok": True, "base_url": base_url, "resolved_home_url": resolved_home,
        "home_status": home_status, "collector": collector_key,
        "card_selector": card_selector, "candidates": candidates,
        "pages_scanned": len(visited), "scan_limit": scan_limit,
        "scan_truncated": bool(queue), "max_depth": max_depth,
        "errors": errors[:20],
    }
