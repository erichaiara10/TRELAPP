"""Iter-25: PropertyType consolidation + scheme enforcement tests."""
import os
import uuid
import pytest
import requests
from dotenv import dotenv_values

env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or env.get("REACT_APP_BACKEND_URL")).rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@trel.com.pg", "password": "Admin@123"}
DEFAULT_TYPES = {
    "House": "lot_section_street",
    "Apartment": "lot_section_street",
    "Town House": "lot_section_street",
    "Commercial": "lot_section_street",
    "Vacant Land – Urban Subdivided": "lot_section_street",
    "Large Land – Portion / Customary": "portion",
}


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json=ADMIN)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def H(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ---- property-types collection ----
def test_get_property_types_public_returns_defaults():
    r = requests.get(f"{API}/property-types")
    assert r.status_code == 200
    docs = r.json()
    names = {d["name"]: d["legal_scheme"] for d in docs}
    for n, scheme in DEFAULT_TYPES.items():
        assert n in names, f"Missing default type: {n}"
        assert names[n] == scheme, f"{n} scheme mismatch: {names[n]} != {scheme}"


def test_create_property_type_unique_and_duplicate_409(H):
    unique_name = f"TEST_Type_{uuid.uuid4().hex[:8]}"
    r = requests.post(f"{API}/property-types", json={"name": unique_name, "legal_scheme": "portion"}, headers=H)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == unique_name
    assert body["legal_scheme"] == "portion"
    assert "id" in body
    tid = body["id"]

    # duplicate
    r2 = requests.post(f"{API}/property-types", json={"name": unique_name}, headers=H)
    assert r2.status_code == 409, r2.text

    # cleanup
    r3 = requests.delete(f"{API}/property-types/{tid}", headers=H)
    assert r3.status_code == 200

    # verify not returned publicly anymore
    r4 = requests.get(f"{API}/property-types")
    assert unique_name not in [d["name"] for d in r4.json()]


def test_delete_property_type_requires_auth():
    r = requests.delete(f"{API}/property-types/nonexistent-id")
    # Unauthenticated → 401/403
    assert r.status_code in (401, 403), r.text


# ---- Property scheme enforcement ----
def _base_property(**over):
    p = {
        "title": "TEST_prop",
        "listing_type": "sale",
        "property_type": "House",
        "price": 500000,
        "location": "Port Moresby",
        "province": "NCD",
        "suburb": "Waigani",
        "bedrooms": 3,
        "bathrooms": 2,
        "total_area_ha": 0.05,
        "allotment_number": "12",
        "section_number": "34",
        "street_name": "Waigani Drive",
        "nearby_landmark": "next to Vision City",
    }
    p.update(over)
    return p


created_property_ids = []


def test_create_property_house_missing_allotment_returns_400(H):
    payload = _base_property(allotment_number="")
    r = requests.post(f"{API}/properties", json=payload, headers=H)
    assert r.status_code == 400
    assert "Lot Number" in r.text or "lot number" in r.text.lower()


def test_create_property_portion_missing_full_portion_returns_400(H):
    payload = _base_property(
        property_type="Large Land – Portion / Customary",
        full_portion_number="",
        allotment_number=None,
        section_number=None,
        street_name=None,
    )
    r = requests.post(f"{API}/properties", json=payload, headers=H)
    assert r.status_code == 400
    assert "Portion" in r.text


def test_create_property_sale_missing_total_area_ha_returns_400(H):
    payload = _base_property(total_area_ha=0)
    r = requests.post(f"{API}/properties", json=payload, headers=H)
    assert r.status_code == 400
    assert "hectare" in r.text.lower() or "total area" in r.text.lower()


def test_create_property_house_success_wipes_portion(H):
    payload = _base_property(full_portion_number="Portion 99")  # should be wiped
    r = requests.post(f"{API}/properties", json=payload, headers=H)
    assert r.status_code == 200, r.text
    body = r.json()
    pid = body["id"]
    created_property_ids.append(pid)
    # GET to verify persisted
    g = requests.get(f"{API}/properties/{pid}")
    assert g.status_code == 200
    d = g.json()
    assert d["property_type"] == "House"
    assert d["allotment_number"] == "12"
    assert d["section_number"] == "34"
    assert d["street_name"] == "Waigani Drive"
    assert d.get("full_portion_number") in (None, "")


def test_create_property_portion_success_wipes_lot_fields(H):
    payload = _base_property(
        property_type="Large Land – Portion / Customary",
        full_portion_number="Portion 123 Milinch Granville",
        allotment_number="X",
        section_number="Y",
        street_name="ShouldBeWiped",
        total_area_ha=2.5,
    )
    r = requests.post(f"{API}/properties", json=payload, headers=H)
    assert r.status_code == 200, r.text
    body = r.json()
    pid = body["id"]
    created_property_ids.append(pid)
    g = requests.get(f"{API}/properties/{pid}").json()
    assert g["property_type"] == "Large Land – Portion / Customary"
    assert g["full_portion_number"] == "Portion 123 Milinch Granville"
    assert g.get("allotment_number") in (None, "")
    assert g.get("section_number") in (None, "")
    assert g.get("street_name") in (None, "")


def test_put_property_scheme_change_lot_to_portion(H):
    # First create House
    payload = _base_property()
    r = requests.post(f"{API}/properties", json=payload, headers=H)
    assert r.status_code == 200
    pid = r.json()["id"]
    created_property_ids.append(pid)

    # PUT change to portion WITHOUT full_portion_number → 400
    r2 = requests.put(f"{API}/properties/{pid}",
                      json={"property_type": "Large Land – Portion / Customary"},
                      headers=H)
    assert r2.status_code == 400, r2.text

    # PUT with full_portion_number → 200, and lot fields wiped
    r3 = requests.put(f"{API}/properties/{pid}",
                      json={"property_type": "Large Land – Portion / Customary",
                            "full_portion_number": "Portion 77"},
                      headers=H)
    assert r3.status_code == 200, r3.text
    g = requests.get(f"{API}/properties/{pid}").json()
    assert g["property_type"] == "Large Land – Portion / Customary"
    assert g["full_portion_number"] == "Portion 77"
    assert g.get("allotment_number") in (None, "")
    assert g.get("section_number") in (None, "")
    assert g.get("street_name") in (None, "")


def test_put_property_strips_legacy_land_category(H):
    payload = _base_property()
    r = requests.post(f"{API}/properties", json=payload, headers=H)
    assert r.status_code == 200
    pid = r.json()["id"]
    created_property_ids.append(pid)

    r2 = requests.put(f"{API}/properties/{pid}",
                      json={"land_category": "should_be_stripped", "title": "TEST_updated"},
                      headers=H)
    assert r2.status_code == 200, r2.text
    g = requests.get(f"{API}/properties/{pid}").json()
    assert "land_category" not in g, f"land_category leaked into DB: {g}"
    assert g["title"] == "TEST_updated"


# ---- AI price analysis picks up street + landmark ----
def test_ai_price_analysis_with_street_and_landmark(H):
    payload = {
        "property_type": "House",
        "listing_type": "sale",
        "price": 500000,
        "province": "NCD",
        "city": "Port Moresby",
        "suburb": "Waigani",
        "bedrooms": 3,
        "street_name": "Waigani Drive",
        "nearby_landmark": "next to Vision City",
    }
    r = requests.post(f"{API}/ai/price-analysis", json=payload, headers=H, timeout=90)
    assert r.status_code == 200, r.text
    data = r.json()
    # Expected common keys — flexible
    assert isinstance(data, dict)
    # At least one price-ish key should exist
    keys = set(data.keys())
    assert keys & {"range_min", "range_max", "average", "verdict", "recommendation"}, f"Unexpected keys: {keys}"


# ---- Teardown ----
def test_zzz_cleanup(H):
    for pid in list(set(created_property_ids)):
        requests.delete(f"{API}/properties/{pid}", headers=H)
