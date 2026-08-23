"""Iteration 29 — regression verification of the 3 iter-28 critical blockers.

1. tenure_type='' coercion on POST /api/properties and /api/properties/duplicate-check
2. non-transactional write fallback on standalone MongoDB (create succeeds)
3. read path: active property visible in GET /api/properties + GET /api/properties/{id};
   drafts visible with ?status=draft
4. staff credential reset (Password@123)
"""
import os
import uuid

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
API = f"{base_url.rstrip('/')}/api"

ADMIN = ("admin@trel.com.pg", "Admin@123")
STAFF = [
    ("director@trel.com.pg", "managing_director"),
    ("sales@trel.com.pg", "sales_agent"),
    ("leasing@trel.com.pg", "leasing_agent"),
    ("marketing@trel.com.pg", "marketing_officer"),
]
TAG = f"TEST_ITER29_{uuid.uuid4().hex[:6]}"


@pytest.fixture(scope="session")
def auth():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": ADMIN[0], "password": ADMIN[1]})
    if r.status_code != 200:
        pytest.fail(f"admin login failed {r.status_code}: {r.text[:300]}")
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
    return s


@pytest.fixture(scope="session")
def created_ids():
    return []


@pytest.fixture(scope="session", autouse=True)
def cleanup(auth, created_ids):
    yield
    for pid in created_ids:
        auth.delete(f"{API}/properties/{pid}")


def payload(**over):
    body = {
        "title": f"{TAG} House",
        "listing_type": "sale",
        "property_type": "House",
        "price": 850000,
        "currency": "PGK",
        "province": "National Capital District",
        "location": "Port Moresby",
        "suburb": "Boroko",
        "allotment_number": "101",
        "section_number": "202",
        "street_name": "Waigani Drive",
        "address": "101/202 Waigani Drive",
        "total_area_ha": 0.05,
        "owner_name": f"{TAG} Owner",
        "owner_email": f"{TAG.lower()}@example.com",
        "owner_phone": "+675 700 22233",
        "owner_relationship": "OWNER",
        "authority_status": "VERIFIED",
        "status": "active",
        "tenure_type": "",
    }
    body.update(over)
    return body


# --- critical#4: staff credentials
@pytest.mark.parametrize("email,role", STAFF)
def test_staff_login(email, role):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": "Password@123"})
    assert r.status_code == 200, f"{email} -> {r.status_code} {r.text[:200]}"
    d = r.json()
    assert d["role"] == role
    assert isinstance(d["token"], str) and d["token"]


# --- critical#1: tenure_type empty-string coercion
def test_duplicate_check_accepts_empty_tenure(auth):
    r = auth.post(f"{API}/properties/duplicate-check",
                  json=payload(allotment_number="9911", section_number="9912",
                               owner_name=f"{TAG} Nobody"))
    assert r.status_code == 200, r.text[:400]
    d = r.json()
    assert d["has_possible_duplicates"] is False
    assert d["candidates"] == []


# --- critical#2 + #3: create on standalone mongo, then read back
def test_create_active_and_read_path(auth, created_ids):
    r = auth.post(f"{API}/properties", json=payload())
    assert r.status_code == 200, r.text[:600]
    d = r.json()
    pid = d["id"]
    created_ids.append(pid)
    assert d["integrated_listing_id"], "integrated_listing_id missing"
    assert d["tenure_type"] is None, f"tenure_type not coerced: {d['tenure_type']!r}"
    assert d["status"] == "active"
    assert d["property_type"] == "House"
    assert float(d["price"]) == 850000
    assert d["suburb"] == "Boroko"

    g = auth.get(f"{API}/properties/{pid}")
    assert g.status_code == 200
    gd = g.json()
    assert gd["title"] == f"{TAG} House"
    assert gd["allotment_number"] == "101"
    assert gd["section_number"] == "202"
    assert gd["owner_name"] == f"{TAG} Owner"

    rows = auth.get(f"{API}/properties?limit=200").json()
    assert any(row["id"] == pid for row in rows), \
        "active property missing from default GET /api/properties"

    pub = requests.get(f"{API}/properties?listing_type=sale&limit=200").json()
    assert any(row["id"] == pid for row in pub), "active property missing from public list"


def test_draft_visible_with_status_filter(auth, created_ids):
    r = auth.post(f"{API}/properties", json=payload(
        title=f"{TAG} Draft", status="draft", authority_status="PENDING",
        allotment_number="301", section_number="302", owner_name=f"{TAG} DraftOwner"))
    assert r.status_code == 200, r.text[:500]
    pid = r.json()["id"]
    created_ids.append(pid)
    drafts = auth.get(f"{API}/properties?status=draft&limit=200").json()
    assert any(row["id"] == pid for row in drafts), "draft not returned by ?status=draft"
    actives = auth.get(f"{API}/properties?limit=200").json()
    assert all(row["id"] != pid for row in actives), "draft leaked into active list"


# --- duplicate detection with override
def test_duplicate_blocked_then_override(auth, created_ids):
    dup = auth.post(f"{API}/properties", json=payload())
    assert dup.status_code == 409, f"expected 409, got {dup.status_code}: {dup.text[:300]}"
    detail = dup.json()["detail"]
    assert detail["code"] == "POSSIBLE_DUPLICATE_PROPERTY"
    assert isinstance(detail.get("candidates"), list) and detail["candidates"]

    ok = auth.post(f"{API}/properties", json=payload(duplicate_override=True))
    assert ok.status_code == 200, ok.text[:400]
    created_ids.append(ok.json()["id"])


def test_same_parcel_different_owner_not_duplicate(auth, created_ids):
    r = auth.post(f"{API}/properties", json=payload(
        title=f"{TAG} OtherOwner", owner_name=f"{TAG} SomeoneElse"))
    assert r.status_code == 200, r.text[:400]
    created_ids.append(r.json()["id"])


# --- customary path
def test_customary_requires_district(auth):
    types = auth.get(f"{API}/property-types").json()
    portion = next((t for t in types if t.get("legal_scheme") == "portion"), None)
    assert portion, "no portion/customary property type available"
    r = auth.post(f"{API}/properties", json=payload(
        property_type_id=portion["id"], property_type=portion["name"],
        allotment_number="", section_number="", street_name="",
        full_portion_number="Portion 9876", district="", status="draft",
        authority_status="PENDING"))
    assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text[:300]}"
    assert "District is required" in r.text


def test_market_evidence_endpoints(auth):
    for path in ("admin/market/summary", "admin/market/listings", "admin/market/sources"):
        r = auth.get(f"{API}/{path}")
        assert r.status_code == 200, f"{path} -> {r.status_code}"
        assert '"_id"' not in r.text
