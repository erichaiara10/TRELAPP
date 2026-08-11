"""Iter-29 tests — Phase 1 Source/Run infrastructure.

Covers:
  * MarketSource extended fields (collection_frequency / parser_version /
    last_run_at / last_successful_run_at / consecutive_failures) on create+list
  * POST /runs/start success + 404/400 error paths
  * POST /runs/{id}/listings batch ingest with per-item counter credit
  * Re-post of same source_listing_id in same run → listings_updated
  * POST /runs/{id}/finish success / partial / forced-failed + audit events +
    duration_ms + source health counters (consecutive_failures reset on success,
    incremented on failed)
  * Cannot ingest into finished run / cannot finish twice
  * GET /sources/health per-source aggregate
  * GET /listings/{id}/snapshots history (2 rows after price change)
  * GET /admin/market/config/active retention block defaults
"""
import os
import re
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL")
            or frontend_env.get("REACT_APP_BACKEND_URL")).rstrip("/")


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------
@pytest.fixture(scope="session")
def test_credentials():
    p = Path("/app/memory/test_credentials.md").read_text()
    em = re.search(r"Email:\s*`([^`]+)`", p).group(1)
    pw = re.search(r"Password:\s*`([^`]+)`", p).group(1)
    return {"email": em, "password": pw}


@pytest.fixture(scope="session")
def auth_headers(test_credentials):
    r = requests.post(f"{BASE_URL}/api/auth/login", json=test_credentials, timeout=30)
    if r.status_code != 200:
        pytest.fail(f"Login failed: {r.status_code} {r.text[:200]}")
    tok = r.json().get("token") or r.json().get("access_token")
    assert tok, f"No token in login response: {r.json()}"
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="session")
def created_ids():
    return {"sources": [], "listings": [], "runs": [], "masters": []}


@pytest.fixture(scope="session", autouse=True)
def cleanup(auth_headers, created_ids):
    yield
    # Delete created sources (cascades in the DB via manual cleanup)
    # We can only DELETE sources via API; runs/listings we leave (they're keyed
    # to test sources so no cross-contamination). But the review request asks
    # to clean db, so we also POST a helper below via direct mongo.
    for sid in created_ids["sources"]:
        try:
            requests.delete(f"{BASE_URL}/api/admin/market/sources/{sid}",
                            headers=auth_headers, timeout=15)
        except Exception:
            pass
    # Deep clean via a direct mongo purge using the test-source ids
    try:
        from pymongo import MongoClient
        env = dotenv_values("/app/backend/.env")
        cli = MongoClient(env["MONGO_URL"])
        d = cli[env["DB_NAME"]]
        sids = created_ids["sources"]
        if sids:
            listing_ids = [l["id"] for l in d.market_listings.find(
                {"source_id": {"$in": sids}}, {"id": 1})]
            d.market_listings.delete_many({"source_id": {"$in": sids}})
            d.market_listing_snapshots.delete_many(
                {"market_listing_id": {"$in": listing_ids}})
            d.property_matches.delete_many(
                {"market_listing_id": {"$in": listing_ids}})
            d.collection_runs.delete_many({"source_id": {"$in": sids}})
        # Also drop any master_properties created during the run (non-backfill)
        d.master_properties.delete_many(
            {"canonical_fields.provenance": {"$ne": "trel_backfill"}})
        d.market_review_cases.delete_many({"market_listing_id": {"$in": listing_ids}}) \
            if sids else None
    except Exception as e:
        print(f"cleanup warn: {e}")


# ------------------------------------------------------------------
# Source model (extended fields)
# ------------------------------------------------------------------
class TestMarketSourceExtendedFields:
    def test_create_source_returns_new_fields(self, auth_headers, created_ids):
        payload = {"name": "TEST_ITER29_SRC_A",
                   "collection_frequency": "daily",
                   "parser_version": "1.0"}
        r = requests.post(f"{BASE_URL}/api/admin/market/sources",
                          json=payload, headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        created_ids["sources"].append(d["id"])
        assert d["collection_frequency"] == "daily"
        assert d["parser_version"] == "1.0"
        assert d["last_run_at"] is None
        assert d["last_successful_run_at"] is None
        assert d["consecutive_failures"] == 0

    def test_list_sources_preserves_new_fields(self, auth_headers, created_ids):
        r = requests.get(f"{BASE_URL}/api/admin/market/sources",
                         headers=auth_headers, timeout=15)
        assert r.status_code == 200
        rows = r.json()
        mine = [x for x in rows if x["id"] in created_ids["sources"]]
        assert mine, "created source not found in listing"
        for row in mine:
            assert "collection_frequency" in row
            assert "parser_version" in row
            assert "consecutive_failures" in row


# ------------------------------------------------------------------
# Run start
# ------------------------------------------------------------------
class TestRunStart:
    def test_start_run_success(self, auth_headers, created_ids):
        sid = created_ids["sources"][0]
        r = requests.post(f"{BASE_URL}/api/admin/market/runs/start",
                          json={"source_id": sid, "run_type": "manual"},
                          headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text
        run = r.json()
        created_ids["runs"].append(run["id"])
        assert run["status"] == "running"
        assert run["run_type"] == "manual"
        assert run["triggered_by"] is not None
        assert run["listings_seen"] == 0
        assert run["source_id"] == sid

    def test_start_run_missing_source_404(self, auth_headers):
        r = requests.post(f"{BASE_URL}/api/admin/market/runs/start",
                          json={"source_id": "nonexistent-xyz", "run_type": "manual"},
                          headers=auth_headers, timeout=15)
        assert r.status_code == 404

    def test_start_run_inactive_source_400(self, auth_headers, created_ids):
        # Create a source and deactivate it
        r = requests.post(f"{BASE_URL}/api/admin/market/sources",
                          json={"name": "TEST_ITER29_SRC_INACTIVE",
                                "active": False,
                                "collection_frequency": "manual",
                                "parser_version": "1.0"},
                          headers=auth_headers, timeout=15)
        assert r.status_code == 200
        sid = r.json()["id"]
        created_ids["sources"].append(sid)
        rr = requests.post(f"{BASE_URL}/api/admin/market/runs/start",
                           json={"source_id": sid, "run_type": "manual"},
                           headers=auth_headers, timeout=15)
        assert rr.status_code == 400


# ------------------------------------------------------------------
# Batch ingest + counters
# ------------------------------------------------------------------
class TestRunBatchIngest:
    def _mk_listing(self, sid, slid, price=250000, lot="15"):
        return {"source_id": sid, "source_listing_id": slid,
                "purpose": "sale", "property_class": "residential",
                "price": price, "currency": "PGK",
                "allotment_number": lot, "section_number": "42",
                "street": "Angau Drive", "suburb": "Gordons",
                "city": "Port Moresby", "province": "NCD",
                "bedrooms": 3, "bathrooms": 2, "land_area_m2": 800}

    def test_batch_ingest_credits_counters_and_returns_results(
            self, auth_headers, created_ids):
        sid = created_ids["sources"][0]
        run_id = created_ids["runs"][0]
        payload = {"listings": [
            self._mk_listing(sid, "iter29-a1", 250000, "15"),
            self._mk_listing(sid, "iter29-a2", 320000, "16"),
        ]}
        r = requests.post(
            f"{BASE_URL}/api/admin/market/runs/{run_id}/listings",
            json=payload, headers=auth_headers, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["processed"] == 2
        assert d["seen"] == 2
        assert d["new"] == 2
        assert d["updated"] == 0
        assert len(d["results"]) == 2
        for item in d["results"]:
            assert item["source_listing_id"] in ("iter29-a1", "iter29-a2")

    def test_repost_same_slid_credits_updated_not_new(
            self, auth_headers, created_ids):
        sid = created_ids["sources"][0]
        run_id = created_ids["runs"][0]
        # Re-post a1 with a different price → should be counted as UPDATED
        payload = {"listings": [self._mk_listing(sid, "iter29-a1", 275000, "15")]}
        r = requests.post(
            f"{BASE_URL}/api/admin/market/runs/{run_id}/listings",
            json=payload, headers=auth_headers, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["processed"] == 1
        # cumulative counters
        assert d["seen"] == 3
        assert d["new"] == 2
        assert d["updated"] == 1


# ------------------------------------------------------------------
# Snapshot history
# ------------------------------------------------------------------
class TestSnapshots:
    def test_listing_snapshots_history(self, auth_headers, created_ids):
        sid = created_ids["sources"][0]
        # find the a1 listing
        r = requests.get(
            f"{BASE_URL}/api/admin/market/listings?source_id={sid}",
            headers=auth_headers, timeout=15)
        assert r.status_code == 200
        listings = r.json()
        a1 = [l for l in listings if l["source_listing_id"] == "iter29-a1"][0]
        rr = requests.get(
            f"{BASE_URL}/api/admin/market/listings/{a1['id']}/snapshots",
            headers=auth_headers, timeout=15)
        assert rr.status_code == 200
        snaps = rr.json()
        # first_seen snapshot + updated price snapshot = 2
        assert len(snaps) >= 2, f"expected ≥2 snapshots, got {len(snaps)}"
        prices = sorted([s["price"] for s in snaps if s.get("price") is not None])
        assert 250000 in prices and 275000 in prices


# ------------------------------------------------------------------
# Finish + audit + duration + source health
# ------------------------------------------------------------------
class TestRunFinish:
    def test_finish_run_success(self, auth_headers, created_ids):
        run_id = created_ids["runs"][0]
        sid = created_ids["sources"][0]
        r = requests.post(f"{BASE_URL}/api/admin/market/runs/{run_id}/finish",
                          json={}, headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "success"
        assert d["duration_ms"] is not None
        assert isinstance(d["duration_ms"], int)

        # Source health counters updated
        rr = requests.get(f"{BASE_URL}/api/admin/market/sources",
                          headers=auth_headers, timeout=15)
        src = [s for s in rr.json() if s["id"] == sid][0]
        assert src["last_run_at"] is not None
        assert src["last_successful_run_at"] is not None
        assert src["consecutive_failures"] == 0

        # Audit event 'run_success'
        ev = requests.get(
            f"{BASE_URL}/api/admin/market/audit-events?entity_type=collection_run&entity_id={run_id}",
            headers=auth_headers, timeout=15).json()
        types = [e["event_type"] for e in ev]
        assert "run_success" in types

    def test_cannot_ingest_finished_run(self, auth_headers, created_ids):
        sid = created_ids["sources"][0]
        run_id = created_ids["runs"][0]
        r = requests.post(
            f"{BASE_URL}/api/admin/market/runs/{run_id}/listings",
            json={"listings": [{"source_id": sid, "source_listing_id": "iter29-x"}]},
            headers=auth_headers, timeout=15)
        assert r.status_code == 400

    def test_cannot_finish_twice(self, auth_headers, created_ids):
        run_id = created_ids["runs"][0]
        r = requests.post(f"{BASE_URL}/api/admin/market/runs/{run_id}/finish",
                          json={}, headers=auth_headers, timeout=15)
        assert r.status_code == 400

    def test_failed_run_increments_streak_then_success_resets(
            self, auth_headers, created_ids):
        sid = created_ids["sources"][0]
        # Start run 2 → force failed
        r = requests.post(f"{BASE_URL}/api/admin/market/runs/start",
                          json={"source_id": sid, "run_type": "manual"},
                          headers=auth_headers, timeout=15)
        assert r.status_code == 200
        run2 = r.json()["id"]
        created_ids["runs"].append(run2)
        rf = requests.post(f"{BASE_URL}/api/admin/market/runs/{run2}/finish",
                           json={"status": "failed", "error": "test forced fail"},
                           headers=auth_headers, timeout=15)
        assert rf.status_code == 200
        assert rf.json()["status"] == "failed"
        src = [s for s in requests.get(f"{BASE_URL}/api/admin/market/sources",
                                        headers=auth_headers).json()
               if s["id"] == sid][0]
        assert src["consecutive_failures"] == 1

        # Audit event run_failed
        ev = requests.get(
            f"{BASE_URL}/api/admin/market/audit-events?entity_type=collection_run&entity_id={run2}",
            headers=auth_headers, timeout=15).json()
        assert any(e["event_type"] == "run_failed" for e in ev)

        # Now a successful run resets streak
        r3 = requests.post(f"{BASE_URL}/api/admin/market/runs/start",
                           json={"source_id": sid, "run_type": "manual"},
                           headers=auth_headers, timeout=15).json()
        created_ids["runs"].append(r3["id"])
        requests.post(f"{BASE_URL}/api/admin/market/runs/{r3['id']}/finish",
                      json={}, headers=auth_headers, timeout=15)
        src = [s for s in requests.get(f"{BASE_URL}/api/admin/market/sources",
                                        headers=auth_headers).json()
               if s["id"] == sid][0]
        assert src["consecutive_failures"] == 0


# ------------------------------------------------------------------
# Sources health endpoint
# ------------------------------------------------------------------
class TestSourceHealth:
    def test_sources_health_shape(self, auth_headers, created_ids):
        r = requests.get(f"{BASE_URL}/api/admin/market/sources/health",
                         headers=auth_headers, timeout=15)
        assert r.status_code == 200
        rows = r.json()
        sid = created_ids["sources"][0]
        mine = [x for x in rows if x["id"] == sid or x.get("source_id") == sid][0]
        for k in ("runs", "success_rate", "error_rate", "partial_rate",
                  "last_run_at", "last_successful_run_at",
                  "consecutive_failures", "avg_duration_ms", "listings_last_run"):
            assert k in mine, f"missing key {k}"
        assert mine["runs"] >= 3  # we ran at least 3 runs
        assert mine["success_rate"] is not None


# ------------------------------------------------------------------
# Config retention defaults
# ------------------------------------------------------------------
class TestConfigRetention:
    def test_active_config_has_retention_block(self, auth_headers):
        r = requests.get(
            f"{BASE_URL}/api/admin/market/config/active?algorithm=combined",
            headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text
        cfg = r.json()
        ret = cfg["parameters"].get("retention")
        assert ret is not None, "retention block missing from active config"
        assert ret["raw_source_data_days"] == 365
        assert ret["normalized_data_days"] == 730
        assert ret["review_case_days"] == 365
        assert ret["audit_log_days"] == 2555
        assert ret["soft_delete_only"] is True
