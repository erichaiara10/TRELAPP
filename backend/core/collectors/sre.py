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
        "search_paths": ["/for-sale", "/for-rent"],
        "card": ".property-item, .property-card, .listing-item, article",
        "url":   "a.property-link, a[href*='/property/'], a.listing-link",
        "title": ".property-title, .listing-title, h2, h3",
        "price": ".price, .property-price, .listing-price",
        "address": ".address, .property-address, .listing-address",
        "description": ".excerpt, .property-description, .listing-description",
        "beds":  ".beds, .bedrooms",
        "baths": ".baths, .bathrooms",
        "land":  ".land-area, .lot-size",
        "building": ".building-area, .floor-area",
        "default_city": "Port Moresby",
        "default_province": "NCD",
        "max_pages_per_purpose": 3,
    }
