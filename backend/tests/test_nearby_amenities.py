"""Tests for POST /api/ai/nearby-amenities (Claude Sonnet 4.5)."""
import os
import re
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or \
           os.environ.get("BASE_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback to frontend .env
    with open("/app/frontend/.env") as f:
        for ln in f:
            if ln.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = ln.split("=", 1)[1].strip().rstrip("/")

URL = f"{BASE_URL}/api/ai/nearby-amenities"
ALLOWED = {"schools", "hospitals", "shopping", "beaches", "transport", "recreation"}


@pytest.fixture(scope="module")
def valid_response():
    payload = {
        "suburb": "Boroko",
        "city": "Port Moresby",
        "province": "National Capital District",
        "property_type": "house",
    }
    r = requests.post(URL, json=payload, timeout=60)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:400]}"
    return r.json()


def test_valid_schema(valid_response):
    d = valid_response
    assert "location_label" in d and isinstance(d["location_label"], str)
    assert "Boroko" in d["location_label"]
    assert "categories" in d and isinstance(d["categories"], list)
    assert "disclaimer" in d and isinstance(d["disclaimer"], str)
    assert len(d["categories"]) >= 3, f"expected >=3 categories, got {len(d['categories'])}"
    assert len(d["categories"]) <= 6


def test_categories_are_allowed_keys(valid_response):
    for cat in valid_response["categories"]:
        assert cat["key"] in ALLOWED, f"unknown key {cat['key']}"
        assert isinstance(cat.get("label"), str) and cat["label"]
        assert isinstance(cat.get("items"), list)
        assert 1 <= len(cat["items"]) <= 4, f"items count out of range: {len(cat['items'])}"


def test_items_have_three_string_fields(valid_response):
    for cat in valid_response["categories"]:
        for it in cat["items"]:
            for field in ("name", "distance_hint", "note"):
                assert field in it
                assert isinstance(it[field], str)
            assert it["name"], "name should not be empty"


def test_no_urls_phones_addresses_in_notes(valid_response):
    url_re = re.compile(r"https?://|www\.", re.I)
    # PNG phones ~ 7-11 digits; look for any sequence of 7+ digits
    phone_re = re.compile(r"\+?\d[\d\s\-]{6,}\d")
    for cat in valid_response["categories"]:
        for it in cat["items"]:
            note = it["note"]
            assert not url_re.search(note), f"URL leaked in note: {note}"
            assert not phone_re.search(note), f"Phone leaked in note: {note}"


def test_missing_city_and_suburb_returns_400():
    r = requests.post(URL, json={"province": "NCD", "property_type": "house"}, timeout=15)
    assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text[:200]}"


def test_only_city_works():
    r = requests.post(URL, json={"city": "Lae", "property_type": "house"}, timeout=60)
    assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text[:200]}"
    d = r.json()
    assert "Lae" in d["location_label"]
    assert isinstance(d["categories"], list) and len(d["categories"]) >= 1
