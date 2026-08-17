"""Tests for the shared parser primitives in `core.collectors._common`.
Fast unit tests — no network or DB — for the contracts every HTTP collector
depends on."""
import asyncio

import pytest

from core.collectors import get_collector, registered
from core.collectors._common import (
    _find_next_page_url,
    infer_subtype,
    parse_address,
    parse_allotment_section,
    parse_bathrooms,
    parse_bedrooms,
    parse_area,
    parse_portion,
    parse_price,
    parse_rent_period,
)


class TestAllotmentSection:
    def test_allot_section_forward(self):
        assert parse_allotment_section("Allotment 14 Section 27 Waigani") == ("14", "27")

    def test_lot_section_forward_with_commas(self):
        assert parse_allotment_section("Lot 5, Sec 9, Boroko") == ("5", "9")

    def test_section_allot_reversed(self):
        assert parse_allotment_section("Section 42 Allotment 8 Gordons") == ("8", "42")

    def test_alphanumeric(self):
        # "Lot 5A" style suffixes preserved
        assert parse_allotment_section("Allot 5A Sec 9B") == ("5A", "9B")

    def test_no_match(self):
        assert parse_allotment_section("plain title without markers") == (None, None)

    def test_none(self):
        assert parse_allotment_section(None) == (None, None)


class TestPortion:
    def test_portion(self):
        assert parse_portion("Portion 1234 vacant land") == "1234"

    def test_portion_none(self):
        assert parse_portion("no portion here") is None


class TestPrice:
    def test_plain_number(self):
        assert parse_price("PGK 850,000") == 850000.0

    def test_with_decimal(self):
        assert parse_price("K 4,500.50 per month") == 4500.5

    def test_dollar_prefix(self):
        assert parse_price("$1,200,000") == 1200000.0

    def test_none(self):
        assert parse_price(None) is None

    def test_no_digits(self):
        assert parse_price("POA") is None

    def test_acceptance_markers_still_rejected_even_with_other_numbers(self):
        assert parse_price("Contact Agent - 3 bedroom home") is None


class TestAreaAndRentPeriod:
    def test_area_accepts_values_below_price_floor(self):
        assert parse_area("Floor area: 85 m²") == 85

    def test_rent_period_is_source_derived(self):
        assert parse_rent_period("K6,000 per month") == "monthly"
        assert parse_rent_period("K900 pw") == "weekly"
        assert parse_rent_period("K6,000") is None


class TestHausplesDetailEnrichment:
    def test_visible_detail_fields_flow_to_normalized_payload(self, monkeypatch):
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
            return await collector._enrich(httpx.AsyncClient(), "https://example.test/property/1",
                                           collector._config(), asyncio.Semaphore(1), 0, None)

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


class TestBedsBaths:
    def test_bedrooms_various(self):
        assert parse_bedrooms("3 bedroom house") == 3
        assert parse_bedrooms("2br apartment") == 2
        assert parse_bedrooms("4 bed") == 4

    def test_bathrooms_various(self):
        assert parse_bathrooms("2 bathroom") == 2
        assert parse_bathrooms("3ba modern") == 3
        assert parse_bathrooms("1 bath cottage") == 1


class TestAddress:
    def test_full(self):
        street, suburb, city, prov = parse_address("12 Main St, Gordons, Port Moresby, NCD")
        assert (street, suburb, city, prov) == ("12 Main St", "Gordons", "Port Moresby", "NCD")

    def test_partial(self):
        street, suburb, city, prov = parse_address("Waigani Drive, Waigani")
        assert street == "Waigani Drive" and suburb == "Waigani"
        assert city is None and prov is None


class TestSubtypeInference:
    def test_house(self):
        cls, sub = infer_subtype("Beautiful 3-bedroom house")
        assert cls == "residential" and sub == "House"

    def test_apartment(self):
        cls, sub = infer_subtype("Modern apartment near CBD")
        assert cls == "residential" and sub == "Apartment"

    def test_land(self):
        cls, sub = infer_subtype("Vacant land block for sale")
        assert cls == "vacant_land" and sub == "Vacant Land"

    def test_warehouse(self):
        cls, sub = infer_subtype("Large warehouse with loading dock")
        assert cls == "commercial_industrial" and sub == "Warehouse"

    def test_none(self):
        cls, sub = infer_subtype("nothing hints at type here")
        assert (cls, sub) == (None, None)


class TestRegistry:
    def test_all_expected_collectors_registered(self):
        keys = {c["key"] for c in registered()}
        expected = {"seed", "hausples_png", "ljhookerpng", "mypnghome",
                    "sre", "dac", "marketmeri"}
        assert expected.issubset(keys), f"missing: {expected - keys}"

    def test_each_http_collector_has_defaults(self):
        # Every non-seed collector must have a non-empty DEFAULT_CONFIG so
        # the "Run" button doesn't crash when a source ships stock.
        for key in ("hausples_png", "ljhookerpng", "mypnghome", "sre", "dac", "marketmeri"):
            Coll = get_collector(key)
            assert Coll is not None, f"{key} not registered"
            cfg = Coll.DEFAULT_CONFIG
            assert cfg.get("base_url", "").startswith("http"), f"{key} missing base_url"
            assert cfg.get("card"), f"{key} missing card selector"
            assert "search_paths" not in cfg, f"{key} still guesses category paths"


class TestDiscoveryOnlyCategoryPages:
    def test_http_collector_without_listing_pages_stops_before_network(self, monkeypatch):
        Coll = get_collector("hausples_png")
        collector = Coll({"name": "No discovery yet", "listing_pages": []})

        class FailClient:
            def __init__(self, *args, **kwargs):
                raise AssertionError("network client created without discovered listing pages")

        monkeypatch.setattr("core.collectors._common.httpx.AsyncClient", FailClient)

        async def collect():
            return [row async for row in collector.iter_listings()]

        assert asyncio.run(collect()) == []


class TestRealPaginationDiscovery:
    def test_rel_next_is_followed(self):
        html = '<html><head><link rel="next" href="/buy/results/2"></head></html>'
        assert _find_next_page_url(html, "https://example.test/buy/results", {}) \
            == "https://example.test/buy/results/2"

    def test_visible_next_is_followed(self):
        html = '<a href="/rent/page-two">Next</a>'
        assert _find_next_page_url(html, "https://example.test/rent", {}) \
            == "https://example.test/rent/page-two"

    def test_no_next_control_never_guesses_query_page(self):
        html = '<article><a href="/property/123-house">House</a></article>'
        assert _find_next_page_url(
            html, "https://example.test/buy?category=homes", {}
        ) is None
