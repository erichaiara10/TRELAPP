"""Iter-35 — Selector Tester expansion across all 6 HTTP collectors."""
import os
import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL")
            or frontend_env.get("REACT_APP_BACKEND_URL")).rstrip("/")

HTTP_KEYS = ["hausples_png", "ljhookerpng", "mypnghome", "sre", "dac", "marketmeri"]


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": "admin@trel.com.pg", "password": "Admin@123"},
                      timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    tok = r.json().get("token") or r.json().get("access_token")
    assert tok, r.json()
    return tok


@pytest.fixture(scope="module")
def client(token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}",
                      "Content-Type": "application/json"})
    return s


class TestCollectorsRegistry:
    def test_list_collectors_has_defaults(self, client):
        r = client.get(f"{BASE_URL}/api/admin/market/collectors")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 7, f"expected 7 collectors, got {len(data)}"
        by_key = {c["key"]: c for c in data}
        # Seed has null default_config
        assert "seed" in by_key
        assert by_key["seed"].get("default_config") is None
        # Each HTTP collector has non-null default_config with required keys
        for k in HTTP_KEYS:
            assert k in by_key, f"missing collector {k}"
            cfg = by_key[k].get("default_config")
            assert isinstance(cfg, dict), f"{k} default_config not dict: {cfg}"
            for req in ("base_url", "card", "search_paths"):
                assert req in cfg and cfg[req], f"{k} missing {req}"

    @pytest.mark.parametrize("key", HTTP_KEYS)
    def test_defaults_endpoint_http(self, client, key):
        r = client.get(f"{BASE_URL}/api/admin/market/collectors/{key}/defaults")
        assert r.status_code == 200, r.text[:200]
        body = r.json()
        assert body["collector"] == key
        assert isinstance(body["default_config"], dict)
        assert "base_url" in body["default_config"]

    def test_defaults_endpoint_seed_404(self, client):
        r = client.get(f"{BASE_URL}/api/admin/market/collectors/seed/defaults")
        assert r.status_code == 404

    def test_defaults_endpoint_unknown_404(self, client):
        r = client.get(f"{BASE_URL}/api/admin/market/collectors/foo/defaults")
        assert r.status_code == 404


class TestGenericSelectorTest:
    @pytest.mark.parametrize("key", HTTP_KEYS)
    def test_probe_each_collector(self, client, key):
        r = client.post(f"{BASE_URL}/api/admin/market/collectors/{key}/test",
                        json={"url": "https://example.com"}, timeout=30)
        assert r.status_code == 200, f"{key}: {r.status_code} {r.text[:200]}"
        body = r.json()
        assert body.get("ok") is True, body
        assert "cards_found" in body
        assert isinstance(body["fields"], dict)
        for f in ("url", "title", "price", "address", "description",
                  "beds", "baths", "land", "building"):
            assert f in body["fields"], f"{key}: missing field {f}"
            entry = body["fields"][f]
            assert "selector" in entry and "matches" in entry and "samples" in entry

    def test_seed_key_returns_404(self, client):
        r = client.post(f"{BASE_URL}/api/admin/market/collectors/seed/test",
                        json={"url": "https://example.com"}, timeout=30)
        assert r.status_code == 404
        assert "Unknown collector" in r.json().get("detail", "")

    def test_invalid_url_400(self, client):
        r = client.post(f"{BASE_URL}/api/admin/market/collectors/mypnghome/test",
                        json={"url": "not-a-url"}, timeout=30)
        assert r.status_code == 400

    def test_legacy_hausples_endpoint(self, client):
        r = client.post(f"{BASE_URL}/api/admin/market/collectors/hausples_png/test",
                        json={"url": "https://example.com"}, timeout=30)
        assert r.status_code == 200
        body = r.json()
        assert body.get("ok") is True
        assert "fields" in body and "cards_found" in body

    def test_selector_override(self, client):
        # example.com has h1; card=h1 title=p should yield cards_found>=1
        r = client.post(f"{BASE_URL}/api/admin/market/collectors/ljhookerpng/test",
                        json={"url": "https://example.com",
                              "selectors": {"card": "h1", "title": "p"}},
                        timeout=30)
        assert r.status_code == 200, r.text[:200]
        body = r.json()
        assert body.get("ok") is True
        # user override should be reflected
        assert body["card_selector"] == "h1"
        assert body["cards_found"] >= 1, body
