"""General website collector driven by staff-confirmed listing pages.

The collector never guesses site paths. Staff enter a website homepage, the
discovery service follows that site's own navigation, and the exact confirmed
listing URLs are stored on the source and collected verbatim.
"""
from __future__ import annotations

from core.collectors import register
from core.collectors._common import HttpListingCollector


@register
class GenericWebCollector(HttpListingCollector):
    key = "generic_web"
    label = "General Website"

    DEFAULT_CONFIG = {
        "card": ".listing-card, .property-card, article, .property, .listing, .card",
        "url": "a[href]",
        "title": ".listing-title, .property-title, .card-title, h3, h2, .title",
        "price": ".listing-price, .property-price, .card-price, .price, [class*='price']",
        "address": ".listing-address, .property-address, .card-address, .address, .location",
        "description": ".listing-description, .property-description, .card-description, .description",
        "beds": ".listing-beds, .beds, [class*='bed']",
        "baths": ".listing-baths, .baths, [class*='bath']",
        "land": ".listing-land, .land-area, [class*='land']",
        "building": ".listing-building, .building-area, [class*='floor'], [class*='building']",
        "detail_selectors": {
            "title": "h1, .property-title, .listing-title",
            "price": ".price, .property-price, .listing-price, [class*='price']",
            "description": ".description, .property-description, .property-details",
            "address": ".address, .property-address, .location",
            "bedrooms": "[class*='bed'] .value, .beds",
            "bathrooms": "[class*='bath'] .value, .baths",
            "land_area": "[class*='land'] .value, .land-area",
            "building_area": "[class*='floor'] .value, [class*='building'] .value",
        },
    }
