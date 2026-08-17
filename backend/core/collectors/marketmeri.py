"""MarketMeri collector — https://www.marketmeri.com

PNG classifieds marketplace. Uses `?page=N` query pagination like Hausples.
"""
from __future__ import annotations

from core.collectors import register
from core.collectors._common import HttpListingCollector


@register
class MarketMeriCollector(HttpListingCollector):
    key = "marketmeri"
    label = "MarketMeri"

    DEFAULT_CONFIG = {
        "base_url": "https://marketmeri.com",
        # MarketMeri's grid-list wraps each ad in .listing-wrapper-grid; the
        # first anchor (a.target-url) points to the detail page and a small
        # cluster of .listing-* spans carries title/price/location.
        "card": ".listing-wrapper-grid",
        "url":   "a.target-url[href]",   # advisory — real logic in _identify_detail_url
        "title": ".listing-title",
        "price": ".listing-price-value, .listing-price",
        "address": ".listing-location",
        "description": ".listing-description",
        "beds":  ".listing-beds, .beds",
        "baths": ".listing-baths, .baths",
        "land":  ".listing-land, .land-area",
        "building": ".listing-floor, .floor-area",

        # Detail-page enrichment — best-effort; ops tune via parser_config.
        "detail_selectors": {
            "title": "h1, .listing-detail-title, .property-title",
            "price": ".listing-detail-price, .price-value, .price",
            "description": ".listing-detail-description, .description",
            "address": ".listing-detail-location, .location",
            "bedrooms": ".listing-detail-bed .value, [class*='bed'] .value",
            "bathrooms": ".listing-detail-bath .value, [class*='bath'] .value",
            "land_area": ".listing-detail-land .value, [class*='land'] .value",
            "building_area": ".listing-detail-floor .value, [class*='floor'] .value",
        },
        "default_city": "Port Moresby",
        "default_province": "NCD",
    }
