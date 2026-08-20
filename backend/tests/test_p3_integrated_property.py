from core.integrated_property_service import (
    IntegratedPropertyService,
    feature_code,
    identifier_scheme,
    norm,
)
from migrations.p3_integrated_property import INDEXES, VALIDATORS


PAYLOAD = {
    "title": "Waigani House",
    "listing_type": "sale",
    "property_type": "House",
    "property_type_id": "type-1",
    "price": 900000,
    "currency": "PGK",
    "bedrooms": 3,
    "bathrooms": 2,
    "parking": 2,
    "area_sqm": 180,
    "province": "National Capital District",
    "province_id": "province-1",
    "location": "Port Moresby",
    "city_id": "city-1",
    "suburb": "Waigani",
    "suburb_id": "suburb-1",
    "street_name": "Waigani Drive",
    "section_number": "42",
    "allotment_number": "15",
    "total_area_ha": 0.08,
    "features": ["Air conditioning", "Security fence"],
    "images": ["https://example.test/one.jpg"],
    "status": "active",
    "owner_name": "Test Owner",
    "owner_relationship": "OWNER",
    "authority_status": "VERIFIED",
}

CONTEXT = {
    "province": {"id": "province-1", "name": "National Capital District"},
    "city": {"id": "city-1", "name": "Port Moresby"},
    "suburb": {"id": "suburb-1", "name": "Waigani"},
    "property_type": {"id": "type-1", "name": "House"},
    "district": None,
    "local_area": None,
}

PARTY = {"id": "party-1", "display_name": "Test Owner"}
USER = {"id": "user-1"}


def test_p3_has_strict_core_property_validator_specs():
    expected = {
        "master_properties", "property_addresses", "property_parcels",
        "property_attributes", "property_parties", "property_documents",
        "listings", "listing_prices", "listing_media", "listing_features",
        "listing_status_history",
    }
    assert set(VALIDATORS) == expected
    assert all(spec["$jsonSchema"]["required"] for spec in VALIDATORS.values())
    assert len(INDEXES) >= 7


def test_graph_uses_one_master_property_and_listing_relationship_chain():
    service = IntegratedPropertyService(None, None)
    graph = service.build_graph(PAYLOAD, USER, CONTEXT, PARTY)
    property_id = graph["master_properties"]["id"]
    listing_id = graph["listings"]["id"]
    for collection in (
        "property_addresses", "property_parcels", "property_attributes",
        "property_parties",
    ):
        assert graph[collection]["property_id"] == property_id
    assert graph["listing_prices"]["listing_id"] == listing_id
    assert graph["listing_status_history"]["listing_id"] == listing_id
    assert graph["property_parties"]["party_id"] == PARTY["id"]
    assert graph["listings"]["transaction_type"] == "SALE"
    assert graph["property_parcels"]["identifier_scheme"] == "URBAN_LOT_SECTION"


def test_normalization_and_identifier_schemes_are_deterministic():
    assert norm("  Waigani   Drive ") == "WAIGANI DRIVE"
    assert feature_code("Air conditioning") == "AIR_CONDITIONING"
    assert identifier_scheme(PAYLOAD) == "URBAN_LOT_SECTION"
    assert identifier_scheme({**PAYLOAD, "full_portion_number": "2145C"}) == "PORTION"
    assert identifier_scheme({
        **PAYLOAD,
        "full_portion_number": "2145C",
        "tenure_type": "CUSTOMARY",
    }) == "CUSTOMARY"
