import asyncio

from core.collectors import get_collector
from core.collectors._common import (
    _canonical_listing_pages, _page_key, parse_area, parse_price,
    parse_rent_period, smart_price_text,
)
from selectolax.parser import HTMLParser


def test_strict_price_rejection_survives_other_numbers():
    assert parse_price("Contact Agent - 3 bedroom home") is None


def test_area_accepts_values_below_price_floor():
    assert parse_area("Floor area: 85 m²") == 85


def test_rent_period_is_source_derived():
    assert parse_rent_period("K6,000 per month") == "monthly"
    assert parse_rent_period("K900 pw") == "weekly"
    assert parse_rent_period("K6,000") is None


def test_hausples_detail_enrichment(monkeypatch):
    html = """
      <html><body>
        <h1>Pinnacle Apartments</h1>
        <div class="property-price">K6,000 per month</div>
        <div class="property-address">Pinnacle Apartments Davetari Road, Boroko, Port Moresby, NCD</div>
        <div class="property-description">Apartment with 3 bedrooms and 2 bathrooms.</div>
        <table>
          <tr><th>Lot Number</th><td>12</td></tr>
          <tr><th>Section Number</th><td>34</td></tr>
          <tr><th>Property Type</th><td>Apartment</td></tr>
          <tr><th>Land Area</th><td>450 m²</td></tr>
          <tr><th>Floor Area</th><td>85 m²</td></tr>
        </table>
      </body></html>
    """

    async def fake_fetch(*args, **kwargs):
        return html, 200

    monkeypatch.setattr("core.collectors._common._fetch_with_retries", fake_fetch)
    collector = get_collector("hausples_png")({"parser_config": {"request_delay_ms": 0}})

    async def enrich():
        import httpx
        return await collector._enrich(
            httpx.AsyncClient(), "https://example.test/property/1",
            collector._config(), asyncio.Semaphore(1), 0, None,
        )

    result, ok = asyncio.run(enrich())
    assert ok
    assert result["price"] == 6000
    assert result["rent_period"] == "monthly"
    assert (result["allotment_number"], result["section_number"]) == ("12", "34")
    assert (result["bedrooms"], result["bathrooms"]) == (3, 2)
    assert (result["land_area_m2"], result["building_area_m2"]) == (450, 85)
    assert result["property_subtype"] == "Apartment"
    assert result["building_name"] == "Pinnacle Apartments"
    assert result["street"] == "Davetari Road"
    assert result["suburb"] == "Boroko"



def test_adaptive_hausples_card_profile_extracts_price_and_identity():
    card = HTMLParser("""
      <article class="s3-rcard">
        <a class="s3-cardlink" href="/buy/alotau/gehua-estate-32141/">
          <h2 class="s3-hl">Land for Sale in Alotau</h2>
          <div class="s3-pr">K800,000</div>
          <div class="s3-ad">Alotau, Milne Bay</div>
        </a>
      </article>
    """).css_first("article")
    collector = get_collector("generic_web")({
        "base_url": "https://www.hausples.com.pg",
        "parser_config": {},
    })
    row, reason = collector._parse_card(
        card, collector._config(), "sale",
        "https://www.hausples.com.pg",
        "https://www.hausples.com.pg/buy/",
    )
    assert reason is None
    assert row["source_listing_id"] == "gehua-estate-32141"
    assert row["price"] == 800000
    assert row["raw_fields"]["title"] == "Land for Sale in Alotau"


def test_legacy_listing_pages_collapse_to_canonical_sale_and_rent():
    pages = _canonical_listing_pages([
        {"listing_url": "https://example.com/buy/", "purpose": "sale"},
        {"listing_url": "https://example.com/buy/house/", "purpose": "sale"},
        {"listing_url": "https://example.com/rent/", "purpose": "rent"},
        {"listing_url": "https://example.com/rent/apartment/", "purpose": "rent"},
    ])
    assert [p["listing_url"] for p in pages] == [
        "https://example.com/buy/", "https://example.com/rent/"
    ]


def test_page_key_detects_equivalent_pagination_urls():
    assert _page_key("https://EXAMPLE.com/buy/?b=2&a=1#top") == (
        "https://example.com/buy?a=1&b=2"
    )


def test_semantic_price_fallback_supports_short_site_classes():
    tree = HTMLParser('<article><div class="s3-pr">PGK 1,250,000</div></article>')
    assert smart_price_text(tree, ".missing") == "PGK 1,250,000"
