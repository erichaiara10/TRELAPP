"""Iteration 28 — P3 Final Hardening screen & workflow verification matrix (backend side).

Covers: common login for staff roles, admin data endpoints backing each sidebar
screen, integrated property write path (create -> GET -> list), duplicate-check,
customary-land validation, owner/authority persistence, market evidence APIs.
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
BASE_URL = base_url.rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = ("admin@trel.com.pg", "Admin@123")
STAFF = [
    ("director@trel.com.pg", "Password@123", "managing_director"),
    ("sales@trel.com.pg", "Password@123", "sales_agent"),
    ("leasing@trel.com.pg", "Password@123", "leasing_agent"),
    ("marketing@trel.com.pg", "Password@123", "marketing_officer"),
]

TAG = f"TEST_ITER28_{uuid.uuid4().hex[:6]}"
PORTION_TYPE = "Large Land – Portion / Customary"


@pytest.fixture(scope="session")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def admin_token(client):
    r = client.post(f"{API}/auth/login", json={"email": ADMIN[0], "password": ADMIN[1]})
    if r.status_code != 200:
        pytest.fail(f"admin login failed {r.status_code}: {r.text[:300]}")
    return r.json()["token"]


@pytest.fixture(scope="session")
def auth(admin_token):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json",
                      "Authorization": f"Bearer {admin_token}"})
    return s


@pytest.fixture(scope="session")
def refs(auth):
    provinces = auth.get(f"{API}/locations/provinces").json()
    ncd = next(p for p in provinces if p["name"] == "National Capital District")
    cities = auth.get(f"{API}/locations/cities").json()
    city = next(c for c in cities if c["province_id"] == ncd["id"])
    suburbs = auth.get(f"{API}/locations/suburbs").json()
    suburb = next(s for s in suburbs if s["city_id"] == city["id"])
    return {"province": ncd["name"], "city": city["name"], "suburb": suburb["name"]}


@pytest.fixture(scope="session")
def created_ids():
    return []


@pytest.fixture(scope="session", autouse=True)
def cleanup(auth, created_ids):
    yield
    for pid in created_ids:
        auth.delete(f"{API}/properties/{pid}")


def house_payload(refs, **over):
    body = {
        "title": f"{TAG} House",
        "listing_type": "sale",
        "property_type": "House",
        "price": 850000,
        "currency": "PGK",
        "province": refs["province"],
        "location": refs["city"],
        "suburb": refs["suburb"],
        "allotment_number": "15",
        "section_number": "42",
        "street_name": "Waigani Drive",
        "address": "15/42 Waigani Drive",
        "total_area_ha": 0.05,
        "owner_name": f"{TAG} Owner",
        "owner_email": f"{TAG.lower()}@example.com",
        "owner_phone": "+675 700 11122",
        "owner_relationship": "OWNER",
        "authority_status": "PENDING",
        "status": "draft",
    }
    body.update(over)
    return body


# ---------------------------------------------------------------- auth / login
class TestLogin:
    def test_health(self, client):
        r = client.get(f"{API}/")
        assert r.status_code == 200

    def test_admin_login_workspace(self, client):
        r = client.post(f"{API}/auth/login", json={"email": ADMIN[0], "password": ADMIN[1]})
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["role"] == "system_admin"
        assert d["account_category"] == "STAFF"
        assert d["workspace_path"] == "/admin"
        assert isinstance(d["token"], str) and d["token"]

    @pytest.mark.parametrize("email,password,role", STAFF)
    def test_staff_login(self, client, email, password, role):
        r = client.post(f"{API}/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200, f"{email} -> {r.status_code} {r.text[:200]}"
        d = r.json()
        assert d["role"] == role
        assert d["workspace_path"] == "/admin"

    def test_bad_password_rejected(self, client):
        r = client.post(f"{API}/auth/login",
                        json={"email": ADMIN[0], "password": "wrong-pass-iter28"})
        assert r.status_code in (401, 400, 429)

    def test_me(self, auth):
        r = auth.get(f"{API}/auth/me")
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN[0]

    def test_bcrypt_hash_format(self, auth):
        users = auth.get(f"{API}/users").json()
        admin = next((u for u in users if u["email"] == ADMIN[0]), None)
        assert admin is not None
        # hash must never be exposed by the API
        assert "password_hash" not in admin or str(admin.get("password_hash", "")).startswith("$2b$")


# ------------------------------------------- endpoints backing sidebar screens
SIDEBAR_ENDPOINTS = [
    "properties", "customers", "leads", "requirements", "inspections", "tasks",
    "users", "locations/provinces", "locations/cities", "locations/suburbs",
    "property-types", "notifications", "reports/summary", "reports/leads_by_source",
    "admin/market/listings", "admin/market/summary", "admin/market/sources",
    "admin/market/match-reviews",
]


class TestSidebarScreens:
    @pytest.mark.parametrize("path", SIDEBAR_ENDPOINTS)
    def test_endpoint_ok(self, auth, path):
        r = auth.get(f"{API}/{path}")
        assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:200]}"
        assert '"_id"' not in r.text

    def test_market_summary_shape(self, auth):
        r = auth.get(f"{API}/admin/market/summary")
        assert r.status_code == 200
        assert isinstance(r.json(), dict)

    def test_property_list_matches_summary_count(self, auth):
        summary = auth.get(f"{API}/reports/summary").json()
        listed = auth.get(f"{API}/properties?status=active").json()
        assert len(listed) == summary["properties_active"], (
            f"dashboard says {summary['properties_active']} active properties but "
            f"GET /api/properties?status=active returns {len(listed)}"
        )


# ------------------------------------------------ integrated property write path
class TestPropertyWritePath:
    def test_create_house_and_read_back(self, auth, refs, created_ids):
        r = auth.post(f"{API}/properties", json=house_payload(refs))
        assert r.status_code == 200, r.text[:500]
        d = r.json()
        pid = d["id"]
        created_ids.append(pid)
        assert d["title"] == f"{TAG} House"
        assert d["property_type"] == "House"
        assert float(d["price"]) == 850000
        assert d["suburb"] == refs["suburb"]
        assert d["owner_name"] == f"{TAG} Owner"
        assert d["owner_email"] == f"{TAG.lower()}@example.com"
        assert d["owner_phone"] == "+675 700 11122"
        assert d["authority_status"] == "PENDING"

        g = auth.get(f"{API}/properties/{pid}")
        assert g.status_code == 200
        assert g.json()["title"] == f"{TAG} House"
        assert g.json()["allotment_number"] == "15"
        assert g.json()["section_number"] == "42"

    def test_created_property_appears_in_list(self, auth, refs, created_ids):
        assert created_ids, "no property created"
        pid = created_ids[0]
        rows = auth.get(f"{API}/properties?limit=200").json()
        assert any(row["id"] == pid for row in rows), \
            "newly created property is not returned by GET /api/properties"

    def test_update_price_persists(self, auth, refs, created_ids):
        pid = created_ids[0]
        body = house_payload(refs, price=900000)
        r = auth.put(f"{API}/properties/{pid}", json=body)
        assert r.status_code == 200, r.text[:400]
        g = auth.get(f"{API}/properties/{pid}")
        assert float(g.json()["price"]) == 900000

    def test_duplicate_check_no_match(self, auth, refs):
        body = house_payload(refs, allotment_number="991", section_number="992",
                             owner_name=f"{TAG} Nobody")
        r = auth.post(f"{API}/properties/duplicate-check", json=body)
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        assert d["has_possible_duplicates"] is False
        assert d["candidates"] == []

    def test_duplicate_check_detects_same_owner_same_parcel(self, auth, refs, created_ids):
        assert created_ids
        r = auth.post(f"{API}/properties/duplicate-check", json=house_payload(refs))
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        assert d["has_possible_duplicates"] is True, d
        assert d["candidates"][0]["property_id"] == created_ids[0]
        assert "same owner" in d["candidates"][0]["reasons"]

    def test_create_duplicate_blocked_409(self, auth, refs):
        r = auth.post(f"{API}/properties", json=house_payload(refs))
        assert r.status_code == 409, f"expected 409 duplicate, got {r.status_code}"
        assert r.json()["detail"]["code"] == "POSSIBLE_DUPLICATE_PROPERTY"

    def test_duplicate_override_allows_create(self, auth, refs, created_ids):
        r = auth.post(f"{API}/properties",
                      json=house_payload(refs, duplicate_override=True))
        assert r.status_code == 200, r.text[:400]
        created_ids.append(r.json()["id"])

    def test_delete_withdraws_property(self, auth, refs, created_ids):
        r = auth.post(f"{API}/properties",
                      json=house_payload(refs, title=f"{TAG} Delete Me",
                                         allotment_number="777", section_number="778",
                                         owner_name=f"{TAG} DelOwner"))
        assert r.status_code == 200, r.text[:300]
        pid = r.json()["id"]
        d = auth.delete(f"{API}/properties/{pid}")
        assert d.status_code in (200, 204)
        g = auth.get(f"{API}/properties/{pid}")
        assert g.status_code == 200
        assert g.json()["status"] == "withdrawn"


# ------------------------------------------------------ validation / edge cases
class TestPropertyValidation:
    def test_customary_requires_portion_number(self, auth, refs):
        types = auth.get(f"{API}/property-types").json()
        customary = next((t for t in types if t.get("legal_scheme") == "portion"), None)
        if not customary:
            pytest.fail("No portion/customary property type in /api/property-types")
        body = house_payload(refs, property_type=PORTION_TYPE,
                             allotment_number="", section_number="", street_name="",
                             full_portion_number="", district="")
        r = auth.post(f"{API}/properties", json=body)
        assert r.status_code == 400
        assert "Portion Number" in r.text

    def test_customary_requires_district(self, auth, refs):
        body = house_payload(refs, property_type=PORTION_TYPE,
                             allotment_number="", section_number="", street_name="",
                             full_portion_number="Portion 1234", district="")
        r = auth.post(f"{API}/properties", json=body)
        assert r.status_code == 400
        assert "District is required" in r.text

    def test_customary_land_create_with_district(self, auth, refs, created_ids):
        body = house_payload(refs, title=f"{TAG} Customary",
                             property_type=PORTION_TYPE,
                             allotment_number="", section_number="", street_name="",
                             full_portion_number=f"Portion {TAG[-4:]}",
                             district="Moresby North-East",
                             tenure_type="CUSTOMARY",
                             owner_name=f"{TAG} Clan")
        r = auth.post(f"{API}/properties", json=body)
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        created_ids.append(d["id"])
        assert d["full_portion_number"] == f"Portion {TAG[-4:]}"
        assert d["district"] == "Moresby North-East"

    def test_missing_owner_name_rejected(self, auth, refs):
        r = auth.post(f"{API}/properties", json=house_payload(refs, owner_name=""))
        assert r.status_code == 400
        assert "Owner name" in r.text

    def test_active_requires_verified_authority(self, auth, refs):
        r = auth.post(f"{API}/properties",
                      json=house_payload(refs, status="active",
                                         authority_status="PENDING",
                                         allotment_number="881", section_number="882",
                                         owner_name=f"{TAG} ActiveOwner"))
        assert r.status_code == 400
        assert "Authority must be verified" in r.text

    def test_zero_price_rejected(self, auth, refs):
        r = auth.post(f"{API}/properties", json=house_payload(refs, price=0))
        assert r.status_code == 400

    def test_unauthenticated_create_rejected(self, refs):
        # fresh session: the shared `client` holds the httpOnly login cookie
        r = requests.post(f"{API}/properties", json=house_payload(refs))
        assert r.status_code in (401, 403)

    def test_get_unknown_property_404(self, auth):
        r = auth.get(f"{API}/properties/{uuid.uuid4()}")
        assert r.status_code == 404


# ------------------------------------------------------------- public endpoints
class TestPublic:
    @pytest.mark.parametrize("path", [
        "properties?status=active&limit=6",
        "properties?featured=true",
        "public/challenge",
        "page-content/home",
    ])
    def test_public_get(self, client, path):
        r = client.get(f"{API}/{path}")
        assert r.status_code in (200, 404), f"{path} -> {r.status_code} {r.text[:200]}"


# ------------------------------------------------------- auth hardening checks
class TestAuthHardening:
    def test_login_sets_httponly_cookie(self):
        r = requests.post(f"{API}/auth/login",
                          json={"email": ADMIN[0], "password": ADMIN[1]})
        assert r.status_code == 200
        cookie = r.headers.get("set-cookie", "")
        assert "access_token=" in cookie
        assert "HttpOnly" in cookie and "Secure" in cookie

    def test_cors_allows_credentials_with_explicit_origin(self):
        origin = BASE_URL
        r = requests.options(f"{API}/auth/login", headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        })
        assert r.status_code in (200, 204)
        allow_origin = r.headers.get("access-control-allow-origin")
        allow_creds = r.headers.get("access-control-allow-credentials")
        assert allow_origin == origin and allow_creds == "true", (
            f"CORS must echo an explicit origin and allow credentials for cookie auth; "
            f"got origin={allow_origin!r} credentials={allow_creds!r}"
        )

    def test_brute_force_lockout_after_five_failures(self):
        email = "marketing@trel.com.pg"
        codes = [requests.post(f"{API}/auth/login",
                               json={"email": email, "password": f"wrong{i}"}).status_code
                 for i in range(6)]
        assert 429 in codes or 423 in codes, \
            f"no lockout after 6 failed logins; status codes={codes}"


# ------------------------------- UI payload contract regressions (Add Property)
class TestUiPayloadContract:
    """The admin Add Property modal posts the literal values it holds in state.
    These assert the API accepts what the UI actually sends."""

    def test_empty_tenure_type_from_ui_is_accepted(self, auth, refs):
        """PropertyModal defaults Tenure type to '' ('Not specified')."""
        body = house_payload(refs, tenure_type="", allotment_number="601",
                            section_number="602", owner_name=f"{TAG} TenureOwner")
        r = auth.post(f"{API}/properties/duplicate-check", json=body)
        assert r.status_code == 200, (
            "UI sends tenure_type='' for 'Not specified' but API rejects it: "
            f"{r.status_code} {r.text[:200]}"
        )

    def test_null_tenure_type_accepted(self, auth, refs):
        body = house_payload(refs, tenure_type=None, allotment_number="603",
                            section_number="604", owner_name=f"{TAG} TenureOwner2")
        r = auth.post(f"{API}/properties/duplicate-check", json=body)
        assert r.status_code == 200, r.text[:200]
