"""Backend tests for Unified Location System (Province → City → Suburb).

Covers:
  - Seed data on startup
  - Public read endpoints for provinces / cities / suburbs
  - Public POST /api/locations/suburbs (no-auth, idempotent, validation)
  - Admin auth guards on /api/admin/locations/*
  - Admin CRUD + cascade delete
  - Backfilled province on existing properties
  - Property model extension (province + location + suburb round-trip)
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@trel.com.pg"
ADMIN_PASSWORD = "Admin@123"


@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    tok = r.json().get("token") or r.json().get("access_token")
    assert tok, f"no token in response: {r.json()}"
    return tok


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="session")
def seeded_ids():
    """Fetch NCD province + Port Moresby city IDs after seed."""
    r = requests.get(f"{API}/locations/provinces", timeout=15)
    assert r.status_code == 200
    provinces = r.json()
    names = {p["name"]: p["id"] for p in provinces}
    expected = {"National Capital District", "Morobe", "Madang", "Western Highlands",
                "East New Britain", "Southern Highlands", "East Sepik", "Enga"}
    missing = expected - set(names.keys())
    assert not missing, f"missing seeded provinces: {missing}"
    ncd_id = names["National Capital District"]
    rc = requests.get(f"{API}/locations/cities", params={"province_id": ncd_id}, timeout=15)
    assert rc.status_code == 200
    cities = rc.json()
    pom = next((c for c in cities if c["name"] == "Port Moresby"), None)
    assert pom, f"Port Moresby not seeded under NCD: {cities}"
    return {"ncd_id": ncd_id, "pom_id": pom["id"], "provinces": names}


# ---------------- SEED ----------------
class TestSeedData:
    def test_provinces_seeded(self, seeded_ids):
        assert len(seeded_ids["provinces"]) >= 8

    def test_pom_suburbs_seeded(self, seeded_ids):
        r = requests.get(f"{API}/locations/suburbs", params={"city_id": seeded_ids["pom_id"]}, timeout=15)
        assert r.status_code == 200
        names = {s["name"] for s in r.json()}
        expected = {"Waigani", "Boroko", "Gordons", "Gerehu", "Ela Beach", "Downtown", "Konedobu", "Hohola"}
        missing = expected - names
        assert not missing, f"missing POM suburbs: {missing}"


# ---------------- PUBLIC USER-ADD SUBURB ----------------
class TestPublicSuburbAdd:
    def test_add_and_idempotent(self, seeded_ids, admin_headers):
        name = f"TESTPySub_{uuid.uuid4().hex[:6]}"
        payload = {"name": name, "city_id": seeded_ids["pom_id"]}
        r = requests.post(f"{API}/locations/suburbs", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["name"] == name
        assert data["source"] == "user"
        sid = data["id"]

        # idempotent: repost same name → returns existing record
        r2 = requests.post(f"{API}/locations/suburbs", json=payload, timeout=15)
        assert r2.status_code == 200
        assert r2.json()["id"] == sid

        # visible in list
        r3 = requests.get(f"{API}/locations/suburbs", params={"city_id": seeded_ids["pom_id"]}, timeout=15)
        assert r3.status_code == 200
        assert any(s["id"] == sid for s in r3.json())

        # cleanup via admin
        d = requests.delete(f"{API}/admin/locations/suburbs/{sid}", headers=admin_headers, timeout=15)
        assert d.status_code == 200

    def test_empty_name_400(self, seeded_ids):
        r = requests.post(f"{API}/locations/suburbs", json={"name": "  ", "city_id": seeded_ids["pom_id"]}, timeout=15)
        assert r.status_code == 400

    def test_invalid_city_404(self):
        r = requests.post(f"{API}/locations/suburbs", json={"name": "X", "city_id": "does-not-exist"}, timeout=15)
        assert r.status_code == 404


# ---------------- ADMIN AUTH GUARDS ----------------
class TestAdminAuthGuards:
    def test_create_province_requires_auth(self):
        r = requests.post(f"{API}/admin/locations/provinces", json={"name": "X"}, timeout=15)
        assert r.status_code == 401

    def test_create_city_requires_auth(self, seeded_ids):
        r = requests.post(f"{API}/admin/locations/cities",
                          json={"name": "X", "province_id": seeded_ids["ncd_id"]}, timeout=15)
        assert r.status_code == 401

    def test_create_suburb_requires_auth(self, seeded_ids):
        r = requests.post(f"{API}/admin/locations/suburbs",
                          json={"name": "X", "city_id": seeded_ids["pom_id"]}, timeout=15)
        assert r.status_code == 401

    def test_delete_province_requires_auth(self, seeded_ids):
        r = requests.delete(f"{API}/admin/locations/provinces/{seeded_ids['ncd_id']}", timeout=15)
        assert r.status_code == 401


# ---------------- ADMIN CRUD + CASCADE ----------------
class TestAdminCRUD:
    def test_full_lifecycle_and_cascade(self, admin_headers):
        # create province
        pname = f"TESTProv_{uuid.uuid4().hex[:6]}"
        rp = requests.post(f"{API}/admin/locations/provinces", json={"name": pname}, headers=admin_headers, timeout=15)
        assert rp.status_code == 200, rp.text
        pid = rp.json()["id"]

        # rename province
        pname2 = pname + "_R"
        rr = requests.put(f"{API}/admin/locations/provinces/{pid}", json={"name": pname2}, headers=admin_headers, timeout=15)
        assert rr.status_code == 200

        # create city under it
        cname = f"TESTCity_{uuid.uuid4().hex[:6]}"
        rc = requests.post(f"{API}/admin/locations/cities",
                           json={"name": cname, "province_id": pid}, headers=admin_headers, timeout=15)
        assert rc.status_code == 200, rc.text
        cid = rc.json()["id"]

        # create suburb under it
        sname = f"TESTSub_{uuid.uuid4().hex[:6]}"
        rs = requests.post(f"{API}/admin/locations/suburbs",
                           json={"name": sname, "city_id": cid}, headers=admin_headers, timeout=15)
        assert rs.status_code == 200, rs.text
        sid = rs.json()["id"]
        assert rs.json()["source"] == "admin"

        # rename suburb
        rs2 = requests.put(f"{API}/admin/locations/suburbs/{sid}",
                           json={"name": sname + "_R"}, headers=admin_headers, timeout=15)
        assert rs2.status_code == 200

        # rename city
        rc2 = requests.put(f"{API}/admin/locations/cities/{cid}",
                           json={"name": cname + "_R"}, headers=admin_headers, timeout=15)
        assert rc2.status_code == 200

        # cascade delete province → city + suburb gone
        rd = requests.delete(f"{API}/admin/locations/provinces/{pid}", headers=admin_headers, timeout=15)
        assert rd.status_code == 200

        # verify cascade
        rc_check = requests.get(f"{API}/locations/cities", params={"province_id": pid}, timeout=15)
        assert rc_check.status_code == 200
        assert all(c["id"] != cid for c in rc_check.json())
        rs_check = requests.get(f"{API}/locations/suburbs", params={"city_id": cid}, timeout=15)
        assert rs_check.status_code == 200
        assert all(s["id"] != sid for s in rs_check.json())

    def test_city_delete_cascades_suburbs(self, admin_headers, seeded_ids):
        # create temp city under NCD
        cname = f"TESTCity_{uuid.uuid4().hex[:6]}"
        rc = requests.post(f"{API}/admin/locations/cities",
                           json={"name": cname, "province_id": seeded_ids["ncd_id"]},
                           headers=admin_headers, timeout=15)
        assert rc.status_code == 200
        cid = rc.json()["id"]

        rs = requests.post(f"{API}/admin/locations/suburbs",
                           json={"name": f"TESTSub_{uuid.uuid4().hex[:6]}", "city_id": cid},
                           headers=admin_headers, timeout=15)
        assert rs.status_code == 200
        sid = rs.json()["id"]

        rd = requests.delete(f"{API}/admin/locations/cities/{cid}", headers=admin_headers, timeout=15)
        assert rd.status_code == 200

        rs_check = requests.get(f"{API}/locations/suburbs", params={"city_id": cid}, timeout=15)
        assert all(s["id"] != sid for s in rs_check.json())


# ---------------- BACKFILL + PROPERTY MODEL ----------------
class TestPropertyIntegration:
    def test_existing_properties_have_province(self):
        r = requests.get(f"{API}/properties", timeout=20)
        assert r.status_code == 200
        props = r.json()
        # accept either wrapped or plain array
        if isinstance(props, dict) and "items" in props:
            props = props["items"]
        assert isinstance(props, list)
        # find at least one Port Moresby prop and one Lae prop and check province
        pom = [p for p in props if (p.get("location") or "").strip().lower() == "port moresby"]
        lae = [p for p in props if (p.get("location") or "").strip().lower() == "lae"]
        if pom:
            assert all(p.get("province") == "National Capital District" for p in pom), \
                f"POM props missing province backfill: {[p.get('province') for p in pom]}"
        if lae:
            assert all(p.get("province") == "Morobe" for p in lae), \
                f"Lae props missing province backfill: {[p.get('province') for p in lae]}"

    def test_create_property_with_location_fields(self, admin_headers):
        payload = {
            "title": f"TEST_Prop_{uuid.uuid4().hex[:6]}",
            "price": 500000,
            "property_type": "house",
            "listing_type": "sale",
            "province": "National Capital District",
            "location": "Port Moresby",
            "suburb": "Waigani",
        }
        r = requests.post(f"{API}/properties", json=payload, headers=admin_headers, timeout=20)
        assert r.status_code in (200, 201), r.text
        pid = r.json().get("id")
        assert pid
        # GET back
        rg = requests.get(f"{API}/properties/{pid}", timeout=15)
        assert rg.status_code == 200
        data = rg.json()
        assert data.get("province") == "National Capital District"
        assert data.get("location") == "Port Moresby"
        assert data.get("suburb") == "Waigani"
        # cleanup
        requests.delete(f"{API}/properties/{pid}", headers=admin_headers, timeout=15)
