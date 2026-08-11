"""MarketMeri collector — https://www.marketmeri.com

PNG classifieds marketplace. Uses `?page=N` query pagination like Hausples.
"""
from __future__ import annotations

from core.collectors import register
from core.collectors._common import HttpListingCollector


@register
class MarketMeriCollector(HttpListingCollector):
    key = "marketmeri"
    label = "MarketMeri"

    DEFAULT_CONFIG = {
        "base_url": "https://www.marketmeri.com",
        # MarketMeri lists real-estate under /category/real-estate — variants
        # for sale + rent are ops-tuneable via parser_config.
        "search_paths": ["/category/real-estate-for-sale",
                         "/category/real-estate-for-rent"],
        "card": ".listing, .ad, .listing-card, article.ad, .classified",
        "url":   "a.ad-link, a.listing-link, a[href*='/ad/'], a[href*='/listing/']",
        "title": ".ad-title, .listing-title, h2, h3",
        "price": ".ad-price, .listing-price, .price",
        "address": ".ad-location, .listing-location, .location",
        "description": ".ad-description, .listing-description, .excerpt, p",
        "beds":  ".beds, .bedrooms",
        "baths": ".baths, .bathrooms",
        "land":  ".land-area, .land-size",
        "building": ".building-area, .floor-area",
        "default_city": "Port Moresby",
        "default_province": "NCD",
        "max_pages_per_purpose": 3,
    }
