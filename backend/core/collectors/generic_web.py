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
        "card": ".s3-rcard, .listing-card, .property-card, article, .property, .listing, .card",
        "url": "a[href]",
        "title": ".s3-hl, .listing-title, .property-title, .card-title, [itemprop='name'], h3, h2, .title",
        "price": ".s3-pr, .listing-price, .property-price, .card-price, .price, [itemprop='price'], [data-price], [class*='price']",
        "address": ".s3-ad, .listing-address, .property-address, .card-address, [itemprop='address'], .address, .location",
        "description": ".listing-description, .property-description, .card-description, .description",
        "beds": ".listing-beds, .beds, [class*='bed']",
        "baths": ".listing-baths, .baths, [class*='bath']",
        "land": ".listing-land, .land-area, [class*='land']",
        "building": ".listing-building, .building-area, [class*='floor'], [class*='building']",
        "detail_selectors": {
            "title": "h1, .property-title, .listing-title",
            "price": ".l3-price, .s3-pr, .price, .property-price, .listing-price, [itemprop='price'], [data-price], [class*='price']",
            "description": ".l3-desc, .description, .property-description, .property-details",
            "address": ".l3-addr, .l3-sub, .address, .property-address, [itemprop='address'], .location",
            "bedrooms": "[class*='bed'] .value, .beds",
            "bathrooms": "[class*='bath'] .value, .baths",
            "land_area": "[class*='land'] .value, .land-area",
            "building_area": "[class*='floor'] .value, [class*='building'] .value",
        },
    }
