from core.integrated_property_service import (
    IntegratedPropertyService,
    feature_code,
    identifier_scheme,
    norm,
)
from migrations.p3_integrated_property import INDEXES, VALIDATORS
from models import PropertyCreate, PropertyReferralCreate
from pydantic import ValidationError
from core.account_policy import account_category, workspace_path
from core.account_policy import require_property_writer
from core.property_repository import PropertyRepository
from fastapi import HTTPException
import asyncio


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


def test_property_dictionary_enums_are_enforced_at_api_boundary():
    for key, value in (
        ("currency", "USD"),
        ("status", "published"),
        ("tenure_type", "LEASE"),
        ("owner_relationship", "BROKER"),
        ("authority_status", "APPROVED"),
    ):
        try:
            PropertyCreate(**{**PAYLOAD, key: value})
        except ValidationError:
            continue
        raise AssertionError(f"Invalid {key} was accepted")


def test_referral_partner_payload_requires_direct_owner_source():
    valid = PropertyReferralCreate(
        owner_name="Direct Owner",
        source_relationship="OWNER",
        direct_from_owner=True,
    )
    assert valid.direct_from_owner is True
    for payload in (
        {"owner_name": "Owner", "source_relationship": "AUTHORISED_AGENT", "direct_from_owner": True},
        {"owner_name": "Owner", "source_relationship": "OWNER", "direct_from_owner": False},
    ):
        try:
            PropertyReferralCreate(**payload)
        except ValidationError:
            continue
        raise AssertionError("Agent-sourced or indirect referral was accepted")


def test_common_login_routes_each_account_category_to_its_workspace():
    assert account_category({"role": "sales_agent"}) == "GUEST"
    assert workspace_path({"account_category": "STAFF"}) == "/admin"
    assert workspace_path({"account_category": "PROPERTY_ADVERTISER"}) == "/advertiser"
    assert workspace_path({"account_category": "REFERRAL_PARTNER"}) == "/referral-partner"


def test_integrated_property_storage_is_the_final_default(monkeypatch):
    monkeypatch.delenv("TREL_PROPERTY_STORAGE_MODE", raising=False)
    assert PropertyRepository(None).storage_mode == "integrated"


def test_referral_partner_cannot_bypass_referral_workflow_to_write_property():
    try:
        asyncio.run(require_property_writer({
            "id": "partner-1", "status": "ACTIVE",
            "account_category": "REFERRAL_PARTNER",
        }))
    except HTTPException as exc:
        assert exc.status_code == 403
        return
    raise AssertionError("Referral Partner was allowed to write a Property directly")
