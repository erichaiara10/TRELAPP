"""Hausples PNG collector — real HTTP + HTML parsing.

Now delegates 100 % of its plumbing (fetch, pagination, card grid extraction,
allotment/section teasing) to `HttpListingCollector` in `_common.py`. This
file just declares the site's default selectors + search paths.

Selectors live in `MarketSource.parser_config` and are inspectable through
the admin "Hausples Selector Tester" modal (`hausples_tester.py`).
"""
from __future__ import annotations

from core.collectors import register
from core.collectors._common import HttpListingCollector


@register
class HausplesCollector(HttpListingCollector):
    key = "hausples_png"
    label = "Hausples PNG"

    DEFAULT_CONFIG = {
        "base_url": "https://www.hausples.com.pg",
        # Listing category URLs are NOT hard-coded here — see the Add Source
        # "Discover Pages" workflow which fetches the live homepage and
        # detects the real category URLs. Discovered URLs are stored on
        # MarketSource.listing_pages and used verbatim by the scraper.
        "card": ".listing-card, .property-card, article",
        "url":   "a.listing-link, a.card-link, a[href*='/property/']",
        "title": ".listing-title, .card-title, h3",
        "price": ".listing-price, .price, .card-price",
        "address": ".listing-address, .address, .card-address",
        "description": ".listing-description, .card-description, p",
        "beds":  ".listing-beds, .beds",
        "baths": ".listing-baths, .baths",
        "land":  ".listing-land, .land-area",
        "building": ".listing-building, .building-area",
        "default_city": "Port Moresby",
        "default_province": "NCD",
        "max_pages_per_purpose": 3,
    }
