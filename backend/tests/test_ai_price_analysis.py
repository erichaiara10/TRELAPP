"""Tests for /api/ai/price-analysis (Claude Sonnet 4.5 via emergentintegrations)."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://req-to-web-1.preview.emergentagent.com").rstrip("/")
ENDPOINT = f"{BASE_URL}/api/ai/price-analysis"


def test_price_analysis_valid_sale():
    payload = {
        "property_type": "House",
        "listing_type": "sale",
        "price": 850000,
        "province": "National Capital District",
        "city": "Port Moresby",
        "suburb": "Boroko",
        "bedrooms": 3,
    }
    r = requests.post(ENDPOINT, json=payload, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    for k in ("range_min", "range_max", "average", "verdict", "recommendation", "comparables", "sample_size"):
        assert k in data, f"missing key {k}"
    assert data["verdict"] in {"fair", "overpriced", "underpriced"}
    assert isinstance(data["comparables"], list)
    assert isinstance(data["range_min"], (int, float))
    assert isinstance(data["range_max"], (int, float))


def test_price_analysis_valid_rent():
    payload = {
        "property_type": "Apartment",
        "listing_type": "rent",
        "price": 3500,
        "city": "Port Moresby",
        "suburb": "Waigani",
        "bedrooms": 2,
    }
    r = requests.post(ENDPOINT, json=payload, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["verdict"] in {"fair", "overpriced", "underpriced"}


def test_price_analysis_zero_price_400():
    r = requests.post(ENDPOINT, json={
        "property_type": "House", "listing_type": "sale",
        "price": 0, "city": "Port Moresby"
    }, timeout=30)
    assert r.status_code == 400


def test_price_analysis_missing_location_400():
    r = requests.post(ENDPOINT, json={
        "property_type": "House", "listing_type": "sale", "price": 500000
    }, timeout=30)
    assert r.status_code == 400


def test_price_analysis_missing_required_422():
    # missing property_type
    r = requests.post(ENDPOINT, json={
        "listing_type": "sale", "price": 500000, "city": "Port Moresby"
    }, timeout=30)
    assert r.status_code in (400, 422)


def test_price_analysis_no_agent_or_id_in_comparables():
    payload = {
        "property_type": "House", "listing_type": "sale",
        "price": 750000, "city": "Port Moresby", "suburb": "Boroko"
    }
    r = requests.post(ENDPOINT, json=payload, timeout=60)
    assert r.status_code == 200
    for c in r.json().get("comparables", []):
        assert "agent" not in c and "owner" not in c and "id" not in c
