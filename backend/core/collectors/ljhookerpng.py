"""LJ Hooker PNG collector — https://www.ljhookerpng.com

Standard LJ Hooker franchise site uses the shared "propertylist"/"card"
markup pattern common to their global network. Pagination is via `/page/N/`
so we use the template mode of `HttpListingCollector`.
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
        "search_paths": ["/properties-for-sale", "/properties-for-rent"],
        # LJ Hooker franchises typically expose /page/N/ style pagination
        "page_url_template": "{base}{path}/page/{page}/",
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
