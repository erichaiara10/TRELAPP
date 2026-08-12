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
        "url":   "a.property-link, .property-title a, a[href*='/property/']",
        "title": ".property-title, .entry-title, h2",
        "price": ".property-price, .price, .property-meta-price",
        "address": ".property-address, .property-location, .address",
        "description": ".property-excerpt, .property-description, .entry-summary",
        "beds":  ".property-meta-beds, .beds",
        "baths": ".property-meta-baths, .baths",
        "land":  ".property-meta-land, .land-area",
        "building": ".property-meta-building, .building-area",
        "default_city": "Port Moresby",
        "default_province": "NCD",
        "max_pages_per_purpose": 3,
    }
