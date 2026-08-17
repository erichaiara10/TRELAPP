import asyncio

from core.collectors import get_collector
from core.collectors._common import parse_area, parse_price, parse_rent_period


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
