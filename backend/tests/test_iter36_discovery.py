"""Iteration 36 — Live listing-page discovery, listing_pages persistence,
legacy migration, and Save-to-source selectors."""
import os
from pathlib import Path
import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL")
            or frontend_env.get("REACT_APP_BACKEND_URL")).rstrip("/")

ADMIN_EMAIL = "admin@trel.com.pg"
ADMIN_PASSWORD = "Admin@123"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                      timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:300]}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def client(token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}",
                      "Content-Type": "application/json"})
    return s


# ---------- ACCEPTANCE: Hausples PNG live discovery ----------
class TestDiscoveryAcceptance:
    def test_hausples_discovery_returns_buy_and_rent(self, client):
        r = client.post(
            f"{BASE_URL}/api/admin/market/collectors/hausples_png/discover",
            json={"base_url": "https://www.hausples.com.pg/"},
            timeout=60,
        )
        assert r.status_code == 200, r.text[:500]
        data = r.json()
        assert data.get("ok") is True, f"ok=False: {data}"
        assert data.get("home_status") == 200
        cands = data.get("candidates") or []
        assert isinstance(cands, list) and cands, "No candidates returned"

        urls = [c.get("listing_url", "") for c in cands]
        # Exact URL match (allow optional trailing slash removed by _clean_url? server returns final_url)
        assert any(u.rstrip("/") == "https://www.hausples.com.pg/buy"
                   for u in urls), f"No /buy/ URL found. URLs: {urls}"
        assert any(u.rstrip("/") == "https://www.hausples.com.pg/rent"
                   for u in urls), f"No /rent/ URL found. URLs: {urls}"

        # No candidate should have legacy reconstructed paths
        for u in urls:
            assert "property-for-sale" not in u, f"legacy path leaked: {u}"
            assert "property-for-rent" not in u, f"legacy path leaked: {u}"

        # /buy/ + /rent/ candidates should have cards_found > 0 and status 200
        for u in cands:
            url = u.get("listing_url", "").rstrip("/")
            if url in ("https://www.hausples.com.pg/buy",
                       "https://www.hausples.com.pg/rent"):
                assert u.get("status") == 200, f"{url} status {u.get('status')}"
                assert u.get("cards_found", 0) > 0, f"{url} cards_found={u.get('cards_found')}"

    def test_discovery_unreachable_url_returns_ok_false(self, client):
        r = client.post(
            f"{BASE_URL}/api/admin/market/collectors/hausples_png/discover",
            json={"base_url": "https://this-domain-does-not-exist-12345.example"},
            timeout=60,
        )
        assert r.status_code == 200, f"Should NOT 500. Got {r.status_code}: {r.text[:300]}"
        data = r.json()
        assert data.get("ok") is False
        assert isinstance(data.get("error"), str) and data["error"]

    def test_discovery_non_http_collector(self, client):
        r = client.post(
            f"{BASE_URL}/api/admin/market/collectors/seed/discover",
            json={"base_url": "https://example.com/"},
            timeout=30,
        )
        assert r.status_code == 200
        data = r.json()
        assert data.get("ok") is False
        assert "not an HTTP scraper" in (data.get("error") or "").lower() or \
               "not an http scraper" in (data.get("error") or "").lower()


# ---------- listing_pages persistence round-trip ----------
class TestListingPagesPersistence:
    def test_listing_pages_round_trip_verbatim(self, client):
        sources = client.get(f"{BASE_URL}/api/admin/market/sources",
                             timeout=30).json()
        assert sources, "No sources seeded"
        # Prefer a Hausples source; fall back to first
        target = next((s for s in sources if s.get("collector") == "hausples_png"),
                      sources[0])
        sid = target["id"]

        payload = {
            "listing_pages": [{
                "category": "buy",
                "category_label": "Buy",
                "purpose": "sale",
                "listing_url": "https://www.hausples.com.pg/buy/",
                "cards_found": 20,
            }]
        }
        r = client.put(f"{BASE_URL}/api/admin/market/sources/{sid}",
                       json=payload, timeout=30)
        assert r.status_code == 200, r.text[:300]

        got = client.get(f"{BASE_URL}/api/admin/market/sources",
                         timeout=30).json()
        src = next(s for s in got if s["id"] == sid)
        pages = src.get("listing_pages") or []
        assert len(pages) == 1
        p = pages[0]
        assert p["listing_url"] == "https://www.hausples.com.pg/buy/"
        assert p["category"] == "buy"
        assert p["purpose"] == "sale"
        assert p["cards_found"] == 20


# ---------- Legacy cleanup migration ----------
class TestLegacyMigration:
    def test_no_legacy_keys_and_listing_pages_present(self, client):
        sources = client.get(f"{BASE_URL}/api/admin/market/sources",
                             timeout=30).json()
        assert sources, "No sources"
        forbidden = {"search_paths", "page_url_template", "purpose_by_path"}
        for s in sources:
            pc = s.get("parser_config") or {}
            leaked = forbidden.intersection(pc.keys())
            assert not leaked, f"Source {s['name']} still has legacy keys: {leaked}"
            assert "listing_pages" in s, f"Source {s['name']} missing listing_pages field"
            assert isinstance(s["listing_pages"], list)


# ---------- Scraper: exact URLs / empty listing_pages ----------
class TestScraperUsesExactUrls:
    def test_collect_with_empty_listing_pages_no_crash(self, client):
        sources = client.get(f"{BASE_URL}/api/admin/market/sources",
                             timeout=30).json()
        # Create a temp HTTP source with empty listing_pages
        payload = {
            "name": "TEST_iter36_empty_pages",
            "base_url": "https://www.hausples.com.pg/",
            "collector": "hausples_png",
            "listing_pages": [],
            "active": True,
        }
        # Cleanup pre-existing
        existing = next((s for s in sources if s["name"] == payload["name"]), None)
        if existing:
            client.delete(f"{BASE_URL}/api/admin/market/sources/{existing['id']}",
                          timeout=30)
        r = client.post(f"{BASE_URL}/api/admin/market/sources",
                        json=payload, timeout=30)
        assert r.status_code == 200, r.text[:300]
        sid = r.json()["id"]
        try:
            r2 = client.post(f"{BASE_URL}/api/admin/market/sources/{sid}/collect",
                             timeout=90)
            assert r2.status_code == 200, f"collect crashed: {r2.status_code} {r2.text[:300]}"
            run = r2.json()
            assert run.get("status") in ("success", "partial")
            assert int(run.get("listings_seen") or 0) == 0
        finally:
            client.delete(f"{BASE_URL}/api/admin/market/sources/{sid}", timeout=30)


# ---------- Save selectors to source ----------
class TestSaveSelectorsToSource:
    def test_save_parser_config_merges(self, client):
        sources = client.get(f"{BASE_URL}/api/admin/market/sources",
                             timeout=30).json()
        target = next((s for s in sources if s.get("collector") == "hausples_png"),
                      sources[0])
        sid = target["id"]
        prev_cfg = dict(target.get("parser_config") or {})

        r = client.post(
            f"{BASE_URL}/api/admin/market/sources/{sid}/parser-config",
            json={"parser_config": {"card": ".custom-card", "title": "h1"}},
            timeout=30,
        )
        assert r.status_code == 200, r.text[:300]
        merged = r.json().get("parser_config") or {}
        assert merged.get("card") == ".custom-card"
        assert merged.get("title") == "h1"
        # Verify previously existing keys still present
        for k, v in prev_cfg.items():
            if k not in {"card", "title"}:
                assert merged.get(k) == v, f"Lost prev key {k}"

        # Restore
        client.post(
            f"{BASE_URL}/api/admin/market/sources/{sid}/parser-config",
            json={"parser_config": prev_cfg or {}}, timeout=30,
        )


# ---------- Regression ----------
class TestRegression:
    def test_collectors_endpoint(self, client):
        r = client.get(f"{BASE_URL}/api/admin/market/collectors", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list) and len(data) >= 7, f"Got {len(data)} collectors"
        http_count = sum(1 for c in data if c.get("default_config"))
        assert http_count >= 6, f"HTTP collectors with defaults: {http_count}"

    def test_sources_endpoint(self, client):
        r = client.get(f"{BASE_URL}/api/admin/market/sources", timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), list) and r.json()

    def test_guidance_run(self, client):
        r = client.post(
            f"{BASE_URL}/api/admin/market/guidance/run",
            json={"purpose": "sale", "property_class": "residential",
                  "suburb": "Gordons", "workflow": "admin"},
            timeout=60,
        )
        assert r.status_code in (200, 400), r.text[:300]
