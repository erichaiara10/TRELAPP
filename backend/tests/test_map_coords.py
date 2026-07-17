"""Backend tests for the new Google Maps coordinate system.

Covers:
  - Property.map_coords is accepted on POST /api/properties, returned by GET,
    and updatable via PUT (verified with a follow-up GET).
  - Setting map_coords to empty string / None clears it.
  - PUT /api/content/site can store site.map_coords.
  - PUT /api/page/contact can store contact.map_coords in sections.
"""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or "http://localhost:8001"
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@trel.com.pg"
ADMIN_PASSWORD = "Admin@123"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ---- Property map_coords ----
class TestPropertyMapCoords:
    def test_create_property_with_coords(self, auth):
        payload = {
            "title": "TEST_MAP_COORDS Property",
            "listing_type": "sale",
            "property_type": "house",
            "price": 500000,
            "location": "Port Moresby",
            "suburb": "Ela Beach",
            "address": "12 Ela Beach Rd",
            "map_coords": "-9.4438,147.1803",
        }
        r = requests.post(f"{API}/properties", json=payload, headers=auth, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["map_coords"] == "-9.4438,147.1803"
        assert data["address"] == "12 Ela Beach Rd"
        pid = data["id"]

        # GET verifies persistence
        g = requests.get(f"{API}/properties/{pid}", timeout=15)
        assert g.status_code == 200
        assert g.json()["map_coords"] == "-9.4438,147.1803"

        # PUT can update coords
        u = requests.put(f"{API}/properties/{pid}", json={"map_coords": "-6.7333,146.9833"}, headers=auth, timeout=15)
        assert u.status_code == 200
        assert u.json()["map_coords"] == "-6.7333,146.9833"

        # GET again to verify
        g2 = requests.get(f"{API}/properties/{pid}", timeout=15)
        assert g2.json()["map_coords"] == "-6.7333,146.9833"

        # Clear coords via empty string
        c = requests.put(f"{API}/properties/{pid}", json={"map_coords": ""}, headers=auth, timeout=15)
        assert c.status_code == 200
        assert c.json().get("map_coords", "") == ""

        # Cleanup
        d = requests.delete(f"{API}/properties/{pid}", headers=auth, timeout=15)
        assert d.status_code == 200

    def test_create_property_without_coords_defaults_none(self, auth):
        payload = {
            "title": "TEST_MAP_COORDS_None Property",
            "listing_type": "rent",
            "property_type": "apartment",
            "price": 3000,
            "location": "Lae",
        }
        r = requests.post(f"{API}/properties", json=payload, headers=auth, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("map_coords") in (None, "")
        pid = data["id"]
        requests.delete(f"{API}/properties/{pid}", headers=auth, timeout=15)


# ---- Content: site.map_coords ----
class TestContentSiteMapCoords:
    def test_put_get_site_map_coords(self, auth):
        # Get current site to preserve on restore
        cur = requests.get(f"{API}/content/site", timeout=15).json().get("value", {})
        new_val = dict(cur)
        new_val["map_coords"] = "-9.4438,147.1803"
        r = requests.put(f"{API}/content/site", json=new_val, headers=auth, timeout=15)
        assert r.status_code == 200
        g = requests.get(f"{API}/content/site", timeout=15).json()
        assert g["value"].get("map_coords") == "-9.4438,147.1803"

        # Restore (remove coords)
        restore = dict(cur)
        restore.pop("map_coords", None)
        requests.put(f"{API}/content/site", json=restore, headers=auth, timeout=15)


# ---- Page: contact.map_coords ----
class TestPageContactMapCoords:
    def test_put_get_contact_map_coords(self, auth):
        # get current
        cur = requests.get(f"{API}/page/contact", timeout=15).json().get("sections", {})
        payload = dict(cur)
        payload["map_coords"] = "-9.4438,147.1803"
        r = requests.put(f"{API}/page/contact", json={"sections": payload}, headers=auth, timeout=15)
        assert r.status_code == 200
        g = requests.get(f"{API}/page/contact", timeout=15).json()
        assert g["sections"].get("map_coords") == "-9.4438,147.1803"

        # Restore
        restore = dict(cur)
        restore.pop("map_coords", None)
        requests.put(f"{API}/page/contact", json={"sections": restore}, headers=auth, timeout=15)
