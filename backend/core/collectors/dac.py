"""Devine & Associates Consulting collector — https://www.dac.com.pg

Boutique valuation + agency. Category pages are supplied by live discovery;
pagination follows only Next links exposed by the returned HTML.
"""
from __future__ import annotations

from core.collectors import register
from core.collectors._common import HttpListingCollector


@register
class DACCollector(HttpListingCollector):
    key = "dac"
    label = "Devine & Associates (dac.com.pg)"

    DEFAULT_CONFIG = {
        "base_url": "https://www.dac.com.pg",
        "card": ".property-listing, .listing-item, article.property, .property",
        "url":   "a[href]",              # advisory — real logic in _identify_detail_url
        "title": ".property-title, .entry-title, h2, h3",
        "price": ".property-price, .price",
        "address": ".property-location, .property-address, .address",
        "description": ".property-excerpt, .entry-content, .description",
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
