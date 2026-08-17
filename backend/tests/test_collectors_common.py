"""Tests for the shared parser primitives in `core.collectors._common`.
Fast unit tests — no network, no DB — just verify the text-extraction helpers
that every HTTP collector depends on."""
import pytest

from core.collectors import get_collector, registered
from core.collectors._common import (
    infer_subtype,
    parse_area,
    parse_address,
    parse_allotment_section,
    parse_bathrooms,
    parse_bedrooms,
    parse_portion,
    parse_price,
    parse_location,
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

    @pytest.mark.parametrize("text", ["POA K500,000", "Contact Agent 900000", "Tender 1,000,000"])
    def test_markers_keep_numeric_price_strictly_rejected(self, text):
        assert parse_price(text) is None

    def test_k_shorthand(self):
        assert parse_price("K850k") == 850000.0


class TestRentAndArea:
    @pytest.mark.parametrize(("text", "expected"), [
        ("K 750 per week", "weekly"), ("K1,500/fortnight", "fortnightly"),
        ("K 4,500 pcm", "monthly"), ("K 80,000 per annum", "annual"),
    ])
    def test_source_derived_period(self, text, expected):
        assert parse_rent_period(text) == expected

    def test_unknown_period_is_not_assumed(self):
        assert parse_rent_period("K 4,500") is None

    def test_explicit_areas_only(self):
        assert parse_area("Land 1,250 m²") == 1250
        assert parse_area("Floor area 320 sqm") == 320
        assert parse_area("K 450,000") is None


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

    def test_building_and_png_location(self):
        parsed = parse_location(
            "Pacific View Apartments, Ela Beach Road, Ela Beach, Port Moresby, NCD",
            default_city="Port Moresby", default_province="NCD",
        )
        assert parsed == {
            "building_name": "Pacific View Apartments", "street": "Ela Beach Road",
            "suburb": "Ela Beach", "local_area": None, "city": "Port Moresby",
            "province": "NCD",
        }

    def test_suburb_only_is_not_mislabelled_as_street(self):
        parsed = parse_location("Waigani", default_city="Port Moresby", default_province="NCD")
        assert parsed["suburb"] == "Waigani"
        assert parsed["street"] is None


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
            # Category paths are discovered and stored on the source; collectors
            # deliberately do not ship guessed ``search_paths``.
            assert "search_paths" not in cfg
