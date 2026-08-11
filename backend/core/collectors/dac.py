"""Devine & Associates Consulting collector — https://www.dac.com.pg

Boutique valuation + agency; typically WordPress-based with `?paged=N`.
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
        "search_paths": ["/property-for-sale", "/property-for-rent"],
        "page_url_template": "{base}{path}/page/{page}/",
        "card": ".property-listing, .listing-item, article.property, .property",
        "url":   "a.property-link, .property-title a, a[href*='/property/']",
        "title": ".property-title, .entry-title, h2, h3",
        "price": ".property-price, .price",
        "address": ".property-location, .property-address, .address",
        "description": ".property-excerpt, .entry-content, .description",
        "beds":  ".beds, .bedrooms",
        "baths": ".baths, .bathrooms",
        "land":  ".land-area, .lot-size",
        "building": ".building-area, .floor-area",
        "default_city": "Port Moresby",
        "default_province": "NCD",
        "max_pages_per_purpose": 3,
    }
