"""Tests for the Sell page benefits migration (Free appraisal -> Professional valuation)."""
import os
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://req-to-web-1.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

EXPECTED = [
    ("Professional valuation", "BadgeCheck"),
    ("Professional photography", "Camera"),
    ("Verified marketing", "Megaphone"),
    ("Dedicated agent support", "Headphones"),
]


def test_sell_benefits_migrated():
    r = requests.get(f"{API}/page/sell")
    assert r.status_code == 200, r.text
    sections = r.json()["sections"]
    benefits = sections.get("benefits")
    assert isinstance(benefits, list), "benefits should be list"
    assert len(benefits) == 4, f"expected 4 benefits, got {len(benefits)}"
    for i, (title, icon) in enumerate(EXPECTED):
        assert benefits[i]["title"] == title, f"idx {i} title got {benefits[i].get('title')}"
        assert benefits[i]["icon"] == icon, f"idx {i} icon got {benefits[i].get('icon')}"


def test_sell_no_free_appraisal():
    r = requests.get(f"{API}/page/sell")
    benefits = r.json()["sections"]["benefits"]
    for b in benefits:
        assert not b.get("title", "").lower().startswith("free appraisal"), b


def test_sell_hero_intro_uses_valuation():
    r = requests.get(f"{API}/page/sell")
    intro = r.json()["sections"]["hero"]["intro"].lower()
    assert "valuation" in intro
    assert "appraisal" not in intro
