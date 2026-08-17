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
        # Listing category URLs are NOT hard-coded — see the Add Source
        # "Discover Pages" workflow. Discovered URLs are stored on
        # MarketSource.listing_pages and used verbatim by the scraper.
        # The card `url` selector below is now advisory only — the shared
        # `_identify_detail_url` picks the most-likely detail anchor from
        # each card using host + path-below-category + slug/id heuristics.
        "card": ".listing-card, .property-card, article, .property, .card",
        "url":   "a[href]",              # advisory — real logic in _identify_detail_url
        "title": ".listing-title, .card-title, h3, h2, .title",
        "price": ".listing-price, .price, .card-price, [class*='price']",
        "address": ".listing-address, .address, .card-address, .location",
        "description": ".listing-description, .card-description, .description",
        "beds":  ".listing-beds, .beds, [class*='bed']",
        "baths": ".listing-baths, .baths, [class*='bath']",
        "land":  ".listing-land, .land-area, [class*='land']",
        "building": ".listing-building, .building-area, [class*='floor'], [class*='building']",
        # Detail-page enrichment — best-effort; ops tune via parser_config.
        "detail_selectors": {
            "title": "h1, .property-title",
            "price": ".price, .property-price, [class*='price']",
            "description": ".description, .property-description, .property-details, [itemprop='description']",
            "address": ".property-address, [itemprop='address'], .address, .location",
            "bedrooms": "[class*='bed'] .value, [itemprop='numberOfRooms'], .beds, [class*='bed']",
            "bathrooms": "[class*='bath'] .value, .baths, [class*='bath']",
            "land_area": "[class*='land'] .value, .land-area, [class*='land']",
            "building_area": "[class*='floor'] .value, [itemprop='floorSize'], [class*='building'] .value",
        },
        "default_city": "Port Moresby",
        "default_province": "NCD",
    }
