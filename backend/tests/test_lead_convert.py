"""API-side tests for the Convert-Lead-to-Property flow (feature added in Leads.jsx).

We create fresh sell_form + contact_form leads via /api/public/leads, then simulate
the front-end conversion path: POST /api/properties, PUT /api/leads/{id} with
status/property_id/property_title. Cleanup at the end.
"""
import os
import re
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN = {"email": "admin@trel.com.pg", "password": "Admin@123"}


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    return sess


@pytest.fixture(scope="module")
def token(s):
    r = s.post(f"{BASE}/api/auth/login", json=ADMIN)
    assert r.status_code == 200, r.text
    return r.json()["access_token"] if "access_token" in r.json() else r.json().get("token")


@pytest.fixture(scope="module")
def auth(s, token):
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


def _get_captcha(s):
    r = s.get(f"{BASE}/api/public/challenge")
    assert r.status_code == 200, r.text
    data = r.json()
    q = data["question"]
    m = re.search(r":\s*([A-Za-z0-9]{5})", q)
    assert m, f"could not parse captcha code from: {q}"
    return data["token"], m.group(1)


# --- Setup lead creation ---
def _create_lead(s, source, name, payload=None, message="Please sell my property"):
    tok, ans = _get_captcha(s)
    body = {
        "source": source,
        "name": name,
        "email": f"TEST_{name.replace(' ','').lower()}@example.com",
        "phone": "+675 1234 5678",
        "message": message,
        "payload": payload or {},
        "verification_token": tok,
        "verification_answer": ans,
    }
    r = s.post(f"{BASE}/api/public/leads", json=body)
    assert r.status_code == 200, r.text
    return r.json()["lead_id"]


class TestConvertLeadFlow:
    created_lead_ids = []
    created_property_ids = []

    def test_01_create_sell_form_lead(self, s):
        payload = {
            "property_type": "house",
            "price": 850000,
            "province": "National Capital District",
            "location": "Port Moresby",
            "suburb": "Boroko",
            "map_coords": "-9.4438,147.1803",
            "photos": [],
        }
        lid = _create_lead(s, "sell_form", "TEST_Seller_One", payload=payload,
                           message="Please sell my house urgently")
        assert lid
        type(self).sell_lead_id = lid
        type(self).created_lead_ids.append(lid)

    def test_02_create_contact_form_lead(self, s):
        lid = _create_lead(s, "contact_form", "TEST_Buyer_One", payload={},
                           message="General enquiry")
        assert lid
        type(self).contact_lead_id = lid
        type(self).created_lead_ids.append(lid)

    def test_03_verify_lead_shape(self, auth):
        r = auth.get(f"{BASE}/api/leads")
        assert r.status_code == 200
        leads = {l["id"]: l for l in r.json()}
        sell = leads[type(self).sell_lead_id]
        assert sell["source"] == "sell_form"
        assert sell["status"] in ("new", "contacted")
        assert sell["payload"]["property_type"] == "house"
        assert sell["payload"]["price"] == 850000
        assert sell["payload"]["suburb"] == "Boroko"
        contact = leads[type(self).contact_lead_id]
        assert contact["source"] == "contact_form"

    def test_04_convert_flow_create_property(self, auth):
        """Simulates front-end: build draft from lead, POST /properties, PUT /leads/{id}."""
        r = auth.get(f"{BASE}/api/leads")
        lead = next(l for l in r.json() if l["id"] == type(self).sell_lead_id)
        p = lead["payload"]
        prop_body = {
            "title": f"{p['suburb']} {p['property_type']}",
            "listing_type": "sale",
            "property_type": p["property_type"],
            "price": p["price"],
            "currency": "PGK",
            "bedrooms": 0, "bathrooms": 0, "parking": 0, "area_sqm": 0,
            "province": p["province"], "location": p["location"], "suburb": p["suburb"],
            "address": "",
            "map_coords": p["map_coords"],
            "description": f"{lead['message']}\n\nOriginal seller: {lead['name']} ({lead['email']})",
            "features": [], "images": [],
            "status": "active", "featured": False, "verified": False,
        }
        r = auth.post(f"{BASE}/api/properties", json=prop_body)
        assert r.status_code in (200, 201), r.text
        prop = r.json()
        assert "id" in prop
        assert prop["title"].endswith("house")
        assert prop["price"] == 850000
        assert prop["province"] == "National Capital District"
        assert prop["location"] == "Port Moresby"
        assert prop["suburb"] == "Boroko"
        assert prop["map_coords"] == "-9.4438,147.1803"
        assert prop["listing_type"] == "sale"
        assert prop["property_type"] == "house"
        type(self).new_prop_id = prop["id"]
        type(self).new_prop_title = prop["title"]
        type(self).created_property_ids.append(prop["id"])

    def test_05_update_lead_to_converted(self, auth):
        r = auth.put(f"{BASE}/api/leads/{type(self).sell_lead_id}", json={
            "status": "converted",
            "property_id": type(self).new_prop_id,
            "property_title": type(self).new_prop_title,
        })
        assert r.status_code == 200, r.text

    def test_06_lead_persisted_as_converted(self, auth):
        r = auth.get(f"{BASE}/api/leads")
        leads = {l["id"]: l for l in r.json()}
        assert type(self).sell_lead_id in leads, "Lead was deleted after conversion!"
        lead = leads[type(self).sell_lead_id]
        assert lead["status"] == "converted"
        assert lead["property_id"] == type(self).new_prop_id
        assert lead["property_title"] == type(self).new_prop_title

    def test_07_property_fetch_matches(self, auth):
        r = auth.get(f"{BASE}/api/properties/{type(self).new_prop_id}")
        assert r.status_code == 200
        p = r.json()
        assert p["title"] == type(self).new_prop_title
        assert p["listing_type"] == "sale"
        assert p["property_type"] == "house"
        assert p["price"] == 850000
        assert p["province"] == "National Capital District"
        assert p["location"] == "Port Moresby"
        assert p["suburb"] == "Boroko"
        assert p["map_coords"] == "-9.4438,147.1803"

    def test_08_contact_lead_still_not_converted(self, auth):
        r = auth.get(f"{BASE}/api/leads")
        contact = next(l for l in r.json() if l["id"] == type(self).contact_lead_id)
        assert contact["status"] != "converted"
        assert not contact.get("property_id")

    def test_99_cleanup(self, auth):
        for pid in type(self).created_property_ids:
            auth.delete(f"{BASE}/api/properties/{pid}")
        for lid in type(self).created_lead_ids:
            auth.delete(f"{BASE}/api/leads/{lid}")
