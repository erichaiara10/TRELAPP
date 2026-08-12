"""LJ Hooker PNG collector — https://www.ljhookerpng.com

Standard LJ Hooker franchise markup. Listing category URLs come from the
"Discover Pages" workflow at Add-Source time — no hard-coded paths here.
"""
from __future__ import annotations

from core.collectors import register
from core.collectors._common import HttpListingCollector


@register
class LJHookerPNGCollector(HttpListingCollector):
    key = "ljhookerpng"
    label = "LJ Hooker PNG"

    DEFAULT_CONFIG = {
        "base_url": "https://www.ljhookerpng.com",
        # LJ Hooker franchises typically expose /page/N/ style pagination
        "card": ".property-list-item, .listing-card, article.property, .propertyItem",
        "url":   "a.property-link, a.listing-link, a[href*='/property/'], a[href*='/listing/']",
        "title": ".property-title, .listing-title, h2, h3",
        "price": ".property-price, .listing-price, .price",
        "address": ".property-address, .listing-address, .address",
        "description": ".property-description, .listing-description, p",
        "beds":  ".beds, .bedrooms, .property-beds",
        "baths": ".baths, .bathrooms, .property-baths",
        "land":  ".land-area, .land",
        "building": ".building-area, .floor-area",
        "default_city": "Port Moresby",
        "default_province": "NCD",
        "max_pages_per_purpose": 3,
    }
