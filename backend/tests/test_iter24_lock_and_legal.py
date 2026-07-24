"""Iter-24 backend tests: Lead lock (converted) & Property legal fields."""
import os
import re
import uuid
import pytest
import requests

def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    # Fallback to /app/frontend/.env
    p = "/app/frontend/.env"
    if os.path.exists(p):
        for line in open(p):
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not set")

BASE_URL = _load_backend_url()


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": "admin@trel.com.pg", "password": "Admin@123"})
    assert r.status_code == 200, r.text
    tok = r.json()["token"]
    s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


def _get_captcha():
    r = requests.get(f"{BASE_URL}/api/public/challenge", timeout=15)
    r.raise_for_status()
    j = r.json()
    # Extract answer from the question text "Type these letters/numbers: ABCDE"
    m = re.search(r":\s*([A-Za-z0-9]+)\s*$", j["question"])
    assert m, j["question"]
    return {"verification_token": j["token"], "verification_answer": m.group(1)}


def _new_public_lead():
    cap = _get_captcha()
    body = {
        "source": "sell_form",
        "name": f"TEST_IT24_{uuid.uuid4().hex[:6]}",
        "email": "t24@example.com",
        "phone": "+67576281552",
        "message": "iter24 seed",
        "payload": {"property_type": "house", "listing_type": "sale",
                    "price": 500000, "province": "National Capital District",
                    "location": "Port Moresby", "suburb": "Gordons"},
        **cap,
    }
    r = requests.post(f"{BASE_URL}/api/public/leads", json=body, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["lead_id"]


# ----------------------------------------------------------------------------- 
# Lead lock behaviour
# -----------------------------------------------------------------------------

class TestLeadLock:
    def test_put_converted_auto_stamps_lock_fields(self, admin_session):
        lead_id = _new_public_lead()
        # Create a stub property to link
        prop_body = {"title": "TEST_IT24_stub", "listing_type": "sale",
                     "property_type": "house", "price": 500000,
                     "location": "Port Moresby", "suburb": "Gordons"}
        pr = admin_session.post(f"{BASE_URL}/api/properties", json=prop_body)
        assert pr.status_code == 200, pr.text
        prop_id = pr.json()["id"]

        # Transition to converted with property_id
        r = admin_session.put(f"{BASE_URL}/api/leads/{lead_id}",
                              json={"status": "converted", "property_id": prop_id})
        assert r.status_code == 200, r.text
        lead = r.json()
        assert lead["status"] == "converted"
        assert lead["converted_property_id"] == prop_id
        assert lead["converted_at"], "converted_at not auto-stamped"

        # Read-back
        all_leads = admin_session.get(f"{BASE_URL}/api/leads").json()
        found = next((x for x in all_leads if x["id"] == lead_id), None)
        assert found and found.get("converted_at")

        # Store on class for follow-ups
        TestLeadLock._locked_lead_id = lead_id
        TestLeadLock._prop_id = prop_id

    def test_put_locked_lead_returns_409(self, admin_session):
        lead_id = getattr(TestLeadLock, "_locked_lead_id", None)
        assert lead_id
        r = admin_session.put(f"{BASE_URL}/api/leads/{lead_id}",
                              json={"status": "new"})
        assert r.status_code == 409, r.text
        assert "locked" in r.json().get("detail", "").lower()

    def test_delete_locked_lead_returns_409_and_persists(self, admin_session):
        lead_id = getattr(TestLeadLock, "_locked_lead_id", None)
        assert lead_id
        r = admin_session.delete(f"{BASE_URL}/api/leads/{lead_id}")
        assert r.status_code == 409, r.text
        # Verify still present
        all_leads = admin_session.get(f"{BASE_URL}/api/leads").json()
        assert any(x["id"] == lead_id for x in all_leads)

    def test_cleanup_stub_property(self, admin_session):
        pid = getattr(TestLeadLock, "_prop_id", None)
        if pid:
            admin_session.delete(f"{BASE_URL}/api/properties/{pid}")


# ----------------------------------------------------------------------------- 
# Property legal fields
# -----------------------------------------------------------------------------

class TestPropertyLegalFields:
    def test_create_and_get_persists_legal_fields(self, admin_session):
        body = {
            "title": "TEST_IT24_legal",
            "listing_type": "sale",
            "property_type": "land",
            "price": 250000,
            "location": "Port Moresby",
            "suburb": "Gordons",
            "province": "National Capital District",
            "land_category": "subdivided_town_land",
            "allotment_number": "15",
            "section_number": "42",
            "total_area_ha": 0.0824,
            "street_name": "Waigani Drive",
            "nearby_landmark": "next to Vision City",
        }
        r = admin_session.post(f"{BASE_URL}/api/properties", json=body)
        assert r.status_code == 200, r.text
        p = r.json()
        pid = p["id"]
        # Verify persist via GET
        g = admin_session.get(f"{BASE_URL}/api/properties/{pid}")
        assert g.status_code == 200
        got = g.json()
        for k in ("land_category", "allotment_number", "section_number",
                  "street_name", "nearby_landmark"):
            assert got.get(k) == body[k], f"{k} not persisted: {got.get(k)}"
        assert float(got.get("total_area_ha")) == 0.0824

        # Cleanup
        admin_session.delete(f"{BASE_URL}/api/properties/{pid}")

    def test_large_portion_variant(self, admin_session):
        body = {
            "title": "TEST_IT24_legal_lp",
            "listing_type": "sale",
            "property_type": "land",
            "price": 350000,
            "location": "Lae",
            "land_category": "large_portion",
            "full_portion_number": "2145C",
            "total_area_ha": 12.5,
        }
        r = admin_session.post(f"{BASE_URL}/api/properties", json=body)
        assert r.status_code == 200, r.text
        pid = r.json()["id"]
        g = admin_session.get(f"{BASE_URL}/api/properties/{pid}").json()
        assert g["land_category"] == "large_portion"
        assert g["full_portion_number"] == "2145C"
        assert float(g["total_area_ha"]) == 12.5
        admin_session.delete(f"{BASE_URL}/api/properties/{pid}")
