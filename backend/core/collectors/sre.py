"""Strickland Real Estate collector — https://www.sre.com.pg

SRE frequently list both sale + rent on the same result grid. When ops know
which path lists what, they set explicit `purpose_by_path` overrides via
`parser_config`.
"""
from __future__ import annotations

from core.collectors import register
from core.collectors._common import HttpListingCollector


@register
class StricklandRECollector(HttpListingCollector):
    key = "sre"
    label = "Strickland Real Estate (sre.com.pg)"

    DEFAULT_CONFIG = {
        "base_url": "https://www.sre.com.pg",
        "card": ".property-item, .property-card, .listing-item, article",
        "url":   "a[href]",              # advisory — real logic in _identify_detail_url
        "title": ".property-title, .listing-title, h2, h3",
        "price": ".price, .property-price, .listing-price",
        "address": ".address, .property-address, .listing-address",
        "description": ".excerpt, .property-description, .listing-description",
        "beds":  ".beds, .bedrooms",
        "baths": ".baths, .bathrooms",
        "land":  ".land-area, .lot-size",
        "building": ".building-area, .floor-area",

        # Detail-page enrichment — best-effort; ops tune via parser_config.
        "detail_selectors": {
            "title": "h1, .property-title, .listing-title",
            "price": ".price, .property-price, [class*='price']",
            "description": ".description, .property-description",
            "address": ".address, .property-address, .location",
            "bedrooms": "[class*='bed'] .value, .beds",
            "bathrooms": "[class*='bath'] .value, .baths",
            "land_area": "[class*='land'] .value, .land-area",
            "building_area": "[class*='floor'] .value, [class*='building'] .value",
        },
        "default_city": "Port Moresby",
        "default_province": "NCD",
    }
