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
    """Walk every anchor on the page. Return a de-duplicated list of
    `{url, text, category_rule}` for links that a) live on the same host,
    b) are not blacklisted, and c) match a category keyword."""
    if not _HAVE_SELECTOLAX:                                            # pragma: no cover
        return []
    tree = HTMLParser(html)
    seen: dict[str, dict] = {}
    for a in tree.css("a[href]"):
        href = (a.attributes.get("href") or "").strip()
        if not href or href.startswith("#") or href.lower().startswith(("javascript:", "mailto:", "tel:")):
            continue
        text = (a.text(strip=True) or "").strip()
        abs_url = urljoin(base_url, href)
        if not _same_host(base_url, abs_url):
            continue
        if _is_blacklisted(text, abs_url):
            continue
        rule = _classify(text, urlparse(abs_url).path)
        if not rule:
            continue
        clean = _clean_url(abs_url)
        # Keep the entry with the most specific rule (earlier position in
        # CATEGORY_RULES wins).
        if clean in seen:
            existing = seen[clean]
            existing_rank = next((i for i, r in enumerate(CATEGORY_RULES)
                                  if r["key"] == existing["rule"]["key"]), 999)
            new_rank = next((i for i, r in enumerate(CATEGORY_RULES)
                             if r["key"] == rule["key"]), 999)
            if new_rank < existing_rank:
                existing["rule"] = rule
                existing["text"] = text or existing["text"]
            continue
        seen[clean] = {"url": clean, "text": text, "rule": rule}
    return list(seen.values())


def _count_cards(html: str, card_selector: str, base_url: str,
                 category_url: str) -> tuple[int, int]:
    """Return `(cards_found, detail_links)` for a candidate listing page.
    A detail link is anything `_identify_detail_url` would accept from
    inside that card — same definition the real scraper uses, so the
    Discover Pages number and the eventual collection can't disagree."""
    if not html or not _HAVE_SELECTOLAX:
        return 0, 0
    tree = HTMLParser(html)
    cards = tree.css(card_selector or "article, .listing, .property")
    detail_links = 0
    for card in cards:
        if _identify_detail_url(card, base_url, category_url):
            detail_links += 1
    return len(cards), detail_links


async def discover_listing_pages(base_url: str, collector_key: str,
                                  parser_config: dict | None = None) -> dict:
    """Public entry — fetch the homepage, extract candidate category links,
    verify each, return grading. Never raises — network / parse errors are
    reported on the top-level `error` key while `candidates` stays a list."""
    if not base_url or not base_url.startswith("http"):
        return {"ok": False, "error": "Valid base URL required"}
    if not _HAVE_SELECTOLAX:                                            # pragma: no cover
        return {"ok": False, "error": "selectolax not installed"}

    Coll = get_collector(collector_key)
    if not Coll or not issubclass(Coll, HttpListingCollector):
        return {"ok": False,
                "error": f"Collector '{collector_key}' is not an HTTP scraper"}

    cfg = dict(Coll.DEFAULT_CONFIG)
    cfg.update(parser_config or {})
    card_selector = cfg.get("card") or "article, .listing, .property"

    headers = {"User-Agent": cfg.get("user_agent",
                                     "TREL-Aggregator/1.0 (+https://trel.com.pg)")}

    import asyncio
    MAX_CANDIDATES = 12          # keep the round-trip under ~30s

    async with httpx.AsyncClient(timeout=8.0, headers=headers,
                                 follow_redirects=True) as client:
        final_home, home_html, home_status = await _fetch(client, base_url)
        if not home_html:
            return {"ok": False, "error": f"Could not reach {base_url} (status={home_status})",
                    "base_url": base_url, "candidates": []}

        anchors = _extract_candidates(home_html, final_home or base_url)
        anchors = anchors[:MAX_CANDIDATES]

        async def _grade(a: dict) -> dict:
            final_url, page_html, status = await _fetch(client, a["url"])
            if not page_html or status >= 400:
                return {
                    "category": a["rule"]["key"],
                    "category_label": a["rule"]["label"],
                    "purpose": a["rule"]["purpose"],
                    "link_text": a["text"],
                    "listing_url": final_url or a["url"],
                    "status": status,
                    "cards_found": 0,
                    "detail_links": 0,
                    "accessible": False,
                    "auto_confirm": False,
                }
            cards_found, detail_links = _count_cards(
                page_html, card_selector,
                base_url=final_home or base_url,
                category_url=final_url or a["url"])
            return {
                "category": a["rule"]["key"],
                "category_label": a["rule"]["label"],
                "purpose": a["rule"]["purpose"],
                "link_text": a["text"],
                "listing_url": final_url,
                "status": status,
                "cards_found": cards_found,
                "detail_links": detail_links,
                "accessible": True,
                "auto_confirm": cards_found >= 1 or detail_links >= 3,
            }

        # Fan out with a small concurrency cap so we don't hammer the target.
        sem = asyncio.Semaphore(4)

        async def _bounded(a):
            async with sem:
                return await _grade(a)

        candidates = await asyncio.gather(*[_bounded(a) for a in anchors])

        # Sort: auto-confirmed → cards → detail_links first
        candidates.sort(key=lambda c: (-int(c.get("auto_confirm", False)),
                                       -c.get("cards_found", 0),
                                       -c.get("detail_links", 0)))

        return {
            "ok": True,
            "base_url": base_url,
            "resolved_home_url": final_home,
            "home_status": home_status,
            "collector": collector_key,
            "card_selector": card_selector,
            "candidates": candidates,
        }
