"""MyPNGHome collector — https://www.mypnghome.com

Boutique PNG portal; typically WordPress-based with `?paged=N` pagination.
Selectors are best-effort — ops tune via `parser_config` when they see the
first live sample.
"""
from __future__ import annotations

from core.collectors import register
from core.collectors._common import HttpListingCollector


@register
class MyPNGHomeCollector(HttpListingCollector):
    key = "mypnghome"
    label = "MyPNGHome"

    DEFAULT_CONFIG = {
        "base_url": "https://www.mypnghome.com",
        # "card": ".property-listing, .listing-item, article.property",
        "url":   "a[href]",              # advisory — real logic in _identify_detail_url
        "title": ".property-title, .entry-title, h2",
        "price": ".property-price, .price, .property-meta-price",
        "address": ".property-address, .property-location, .address",
        "description": ".property-excerpt, .property-description, .entry-summary",
        "beds":  ".property-meta-beds, .beds",
        "baths": ".property-meta-baths, .baths",
        "land":  ".property-meta-land, .land-area",
        "building": ".property-meta-building, .building-area",

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
