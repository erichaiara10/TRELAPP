"""Iteration 37 — Bulk Rediscover feature tests.

Covers:
- POST /admin/market/sources/rediscover-all
- PUT  /admin/market/sources/{sid}/listing-pages
- Audit log entries
"""
import os
import time
from pathlib import Path
import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
BASE_URL = (
    os.environ.get("REACT_APP_BACKEND_URL")
    or frontend_env.get("REACT_APP_BACKEND_URL")
).rstrip("/")

CREDS = {"email": "admin@trel.com.pg", "password": "Admin@123"}


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json=CREDS, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:300]}"
    tok = r.json().get("token") or r.json().get("access_token")
    assert tok, f"no token in login response: {r.json()}"
    return tok


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def rediscover_response(headers):
    """Run the bulk rediscover once; reuse for multiple assertions."""
    r = requests.post(
        f"{BASE_URL}/api/admin/market/sources/rediscover-all",
        headers=headers,
        json={},
        timeout=180,
    )
    assert r.status_code == 200, f"{r.status_code}: {r.text[:500]}"
    return r.json()


# ---------- rediscover-all ----------
class TestRediscoverAll:
    def test_schema(self, rediscover_response):
        data = rediscover_response
        for k in ("total", "with_changes", "no_changes", "errored", "skipped", "diffs"):
            assert k in data, f"missing key {k}"
        assert isinstance(data["diffs"], list)
        assert data["total"] == len(data["diffs"])
        # Bucket totals should sum
        assert (
            data["with_changes"] + data["no_changes"] + data["errored"] + data["skipped"]
            == data["total"]
        )

    def test_diff_entry_shape(self, rediscover_response):
        for d in rediscover_response["diffs"]:
            for k in ("source_id", "source_name", "collector", "base_url",
                      "ok", "before", "added", "removed", "unchanged"):
                assert k in d, f"diff missing {k}: {d}"
            assert isinstance(d["added"], list)
            assert isinstance(d["removed"], list)
            assert isinstance(d["unchanged"], list)

    def test_skipped_reasons(self, rediscover_response):
        for d in rediscover_response["diffs"]:
            if d.get("skipped"):
                assert d["ok"] is False
                assert d.get("reason") in ("Not an HTTP scraper", "No base URL configured")

    def test_hausples_suggested_buy_and_rent(self, rediscover_response):
        haus = [d for d in rediscover_response["diffs"]
                if d.get("source_name") == "Hausples PNG"]
        assert haus, "No 'Hausples PNG' diff entry present"
        h = haus[0]
        assert h["ok"] is True, f"Hausples not ok: {h.get('error')}"
        suggested_urls = [s.get("listing_url") for s in (h.get("suggested") or [])]
        assert "https://www.hausples.com.pg/buy/" in suggested_urls, suggested_urls
        assert "https://www.hausples.com.pg/rent/" in suggested_urls, suggested_urls
        for u in suggested_urls:
            assert "/property-for-sale" not in u
            assert "/property-for-rent" not in u

    def test_graceful_errors_do_not_500(self, rediscover_response):
        """Some sources may be unreachable — they must produce ok=false + error string,
        not raise a 500 on the whole request."""
        errored = [d for d in rediscover_response["diffs"]
                   if not d.get("ok") and not d.get("skipped")]
        for d in errored:
            assert d.get("error"), f"errored entry has no error msg: {d}"


# ---------- PUT listing-pages ----------
class TestApplyListingPages:
    @pytest.fixture(scope="class")
    def hausples_sid(self, headers):
        r = requests.get(f"{BASE_URL}/api/admin/market/sources",
                         headers=headers, timeout=30)
        assert r.status_code == 200
        srcs = r.json()
        haus = [s for s in srcs if s.get("name") == "Hausples PNG"]
        assert haus, "Hausples PNG source not seeded"
        return haus[0]["id"], haus[0].get("listing_pages") or []

    def test_404_on_unknown(self, headers):
        r = requests.put(
            f"{BASE_URL}/api/admin/market/sources/nonexistent-xyz/listing-pages",
            headers=headers, json={"listing_pages": []}, timeout=30,
        )
        assert r.status_code == 404
        assert "not found" in r.text.lower()

    def test_400_on_non_list(self, headers, hausples_sid):
        sid, _ = hausples_sid
        r = requests.put(
            f"{BASE_URL}/api/admin/market/sources/{sid}/listing-pages",
            headers=headers, json={"listing_pages": "not-a-list"}, timeout=30,
        )
        assert r.status_code == 400
        assert "array" in r.text.lower()

    def test_apply_then_verify_and_restore(self, headers, hausples_sid):
        sid, original = hausples_sid
        # Apply a single entry
        entry = {
            "category": "buy", "category_label": "Buy",
            "purpose": "sale",
            "listing_url": "https://www.hausples.com.pg/buy/",
            "cards_found": 20, "detail_links": 0,
        }
        r = requests.put(
            f"{BASE_URL}/api/admin/market/sources/{sid}/listing-pages",
            headers=headers, json={"listing_pages": [entry]}, timeout=30,
        )
        assert r.status_code == 200, r.text[:400]
        updated = r.json()
        assert isinstance(updated.get("listing_pages"), list)
        assert len(updated["listing_pages"]) == 1
        assert updated["listing_pages"][0]["listing_url"] == entry["listing_url"]

        # GET verifies persistence
        r2 = requests.get(f"{BASE_URL}/api/admin/market/sources",
                          headers=headers, timeout=30)
        assert r2.status_code == 200
        haus = [s for s in r2.json() if s["id"] == sid][0]
        assert len(haus["listing_pages"]) == 1
        assert haus["listing_pages"][0]["listing_url"] == entry["listing_url"]

        # Empty-list clears
        r3 = requests.put(
            f"{BASE_URL}/api/admin/market/sources/{sid}/listing-pages",
            headers=headers, json={"listing_pages": []}, timeout=30,
        )
        assert r3.status_code == 200
        assert r3.json()["listing_pages"] == []

        # Restore original
        r4 = requests.put(
            f"{BASE_URL}/api/admin/market/sources/{sid}/listing-pages",
            headers=headers, json={"listing_pages": original}, timeout=30,
        )
        assert r4.status_code == 200


# ---------- audit ----------
class TestAudit:
    def test_audit_entries_present(self, headers, rediscover_response):
        r = requests.get(f"{BASE_URL}/api/admin/market/audit-log?limit=25",
                         headers=headers, timeout=30)
        if r.status_code == 404:
            pytest.skip("audit-log endpoint not available")
        assert r.status_code == 200, r.text[:300]
        entries = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
        actions = {e.get("action") for e in entries}
        assert "sources_rediscover_all" in actions, actions
        # source_listing_pages_updated should also exist (from TestApplyListingPages)
        # but ordering across classes is not guaranteed; do a soft check.
        if "source_listing_pages_updated" not in actions:
            print("NOTE: source_listing_pages_updated not in latest 25 entries")
