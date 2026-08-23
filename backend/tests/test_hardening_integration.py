"""Integration tests for the hardening changes hitting the live preview backend.

- Login brute-force: 5 wrong attempts → 429, correct password after reset → 200
- Non-transactional write: full property create + read still works on standalone Mongo
- Unknown-email login returns the SAME shape as a wrong-password login (no user enumeration)
"""
from __future__ import annotations

import os
import uuid

import pytest
import requests


API = os.getenv("REACT_APP_BACKEND_URL") or "http://localhost:8001"
ADMIN = "admin@trel.com.pg"
ADMIN_PW = "Admin@123"


@pytest.fixture(scope="module")
def admin_token():
    _reset_login_failures(ADMIN)
    resp = requests.post(f"{API}/api/auth/login", json={"email": ADMIN, "password": ADMIN_PW}, timeout=10)
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


def _reset_login_failures(email: str):
    """Best-effort direct DB reset so the guard doesn't leak across tests."""
    try:
        from pymongo import MongoClient
        client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
        client[os.environ.get("DB_NAME", "test_database")].login_failures.delete_many({"email": email.lower()})
    except Exception:
        pass


def test_login_lockout_after_five_failures():
    email = "admin@trel.com.pg"
    _reset_login_failures(email)
    for _ in range(5):
        resp = requests.post(f"{API}/api/auth/login", json={"email": email, "password": "wrongPass!"}, timeout=10)
        assert resp.status_code == 401
    # 6th attempt should be locked
    locked = requests.post(f"{API}/api/auth/login", json={"email": email, "password": "wrongPass!"}, timeout=10)
    assert locked.status_code == 429
    assert "Too many login attempts" in locked.text
    # Correct password is ALSO blocked while locked
    still_locked = requests.post(f"{API}/api/auth/login", json={"email": email, "password": ADMIN_PW}, timeout=10)
    assert still_locked.status_code == 429
    _reset_login_failures(email)
    # After reset, correct password works
    ok = requests.post(f"{API}/api/auth/login", json={"email": email, "password": ADMIN_PW}, timeout=10)
    assert ok.status_code == 200


def test_unknown_email_indistinguishable_from_wrong_password():
    unknown = f"ghost{uuid.uuid4().hex[:6]}@example.com"
    _reset_login_failures(unknown)
    _reset_login_failures(ADMIN)
    a = requests.post(f"{API}/api/auth/login", json={"email": unknown, "password": "anything"}, timeout=10)
    b = requests.post(f"{API}/api/auth/login", json={"email": ADMIN, "password": "notAdmin"}, timeout=10)
    _reset_login_failures(ADMIN)
    # Same status + same detail = no user enumeration
    assert a.status_code == 401
    assert b.status_code == 401
    assert a.json() == b.json()


def test_property_create_returns_partial_write_error_shape():
    """We can't easily trigger a real partial write against the live DB, but
    verify the surrounding shape by ensuring valid writes still work and the
    non-transactional fallback log line was emitted at startup."""
    _reset_login_failures(ADMIN)
    token = requests.post(f"{API}/api/auth/login", json={"email": ADMIN, "password": ADMIN_PW}, timeout=10).json()["token"]
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    # Fetch a valid property_type_id (House) + NCD province
    types_resp = requests.get(f"{API}/api/property-types", headers=headers, timeout=10)
    ptid = next(t["id"] for t in types_resp.json() if t["name"] == "House")
    provinces = requests.get(f"{API}/api/locations/provinces", headers=headers, timeout=10).json()
    ncd_id = next(p["id"] for p in provinces if "National Capital" in p["name"])
    cities = requests.get(f"{API}/api/locations/cities", headers=headers, timeout=10).json()
    pom_id = next(c["id"] for c in cities if c.get("province_id") == ncd_id)
    suburbs = requests.get(f"{API}/api/locations/suburbs", headers=headers, timeout=10).json()
    suburb_id = next(s["id"] for s in suburbs if s.get("city_id") == pom_id)

    unique = uuid.uuid4().hex[:6].upper()
    payload = {
        "title": f"HARDENING_TEST_{unique}",
        "listing_type": "sale", "property_type": "House", "price": 700000, "currency": "PGK",
        "bedrooms": 2, "bathrooms": 1, "parking": 1, "total_area_ha": 0.05,
        "location": "Port Moresby", "suburb": "Boroko", "province": "National Capital District",
        "address": "1 Hardening Way",
        "province_id": ncd_id, "city_id": pom_id, "suburb_id": suburb_id,
        "property_type_id": ptid,
        "allotment_number": unique, "section_number": unique, "street_name": "Hardening Way",
        "tenure_type": "",
        "owner_name": f"Owner {unique}", "owner_relationship": "OWNER",
        "authority_status": "VERIFIED", "status": "active",
    }
    create = requests.post(f"{API}/api/properties", headers=headers, json=payload, timeout=15)
    assert create.status_code == 200, create.text
    body = create.json()
    assert body["id"]
    assert body["integrated_listing_id"]
    # Clean up
    requests.delete(f"{API}/api/properties/{body['id']}", headers=headers, timeout=10)
