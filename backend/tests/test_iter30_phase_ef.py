"""Iter-30 — Phase E/F: Collectors + Analytics + Public Price Compare + Scheduler."""
import os
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")).rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@trel.com.pg"
ADMIN_PASSWORD = "Admin@123"

# ----- session shared state -----
_state = {"token": None, "source_id": None, "second_source_id": None}


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin_token(client):
    if _state["token"]:
        return _state["token"]
    r = client.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text[:200]}"
    tok = r.json().get("token") or r.json().get("access_token")
    assert tok, f"No token in login response: {r.json()}"
    _state["token"] = tok
    return tok


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# =====================================================================
# 1. COLLECTORS REGISTRY
# =====================================================================
class TestCollectorsRegistry:
    def test_list_collectors(self, client, auth_headers):
        r = client.get(f"{API}/admin/market/collectors", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        keys = {c["key"] for c in data}
        assert "seed" in keys
        assert "hausples_png" in keys
        seed = next(c for c in data if c["key"] == "seed")
        assert seed["requires_network"] is False
        assert "TREL Seed" in seed["label"] or "seed" in seed["label"].lower()
        haus = next(c for c in data if c["key"] == "hausples_png")
        assert haus["requires_network"] is True


# =====================================================================
# 2. ONE-SHOT COLLECT (seed) + IDEMPOTENCY
# =====================================================================
class TestCollectorRun:
    def test_create_seed_source(self, client, auth_headers):
        payload = {
            "name": "TEST_ITER30_SEED",
            "base_url": "https://seed.trel.pg",
            "active": True,
            "collector": "seed",
            "collection_frequency": "manual",
            "parser_version": "1.0",
        }
        r = client.post(f"{API}/admin/market/sources", json=payload, headers=auth_headers)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        doc = r.json()
        assert doc["collector"] == "seed"
        assert "id" in doc
        _state["source_id"] = doc["id"]

    def test_first_collect_creates_new(self, client, auth_headers):
        sid = _state["source_id"]
        assert sid, "source not created"
        r = client.post(f"{API}/admin/market/sources/{sid}/collect", headers=auth_headers)
        assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"
        run = r.json()
        assert run["status"] == "success", f"run={run}"
        assert run.get("duration_ms") is not None and int(run["duration_ms"]) > 0
        assert int(run.get("listings_seen") or 0) == 12
        assert int(run.get("listings_new") or 0) == 12
        # matches_created should equal listings_new for a fresh seed
        assert int(run.get("matches_created") or 0) == 12

    def test_second_collect_is_idempotent(self, client, auth_headers):
        sid = _state["source_id"]
        r = client.post(f"{API}/admin/market/sources/{sid}/collect", headers=auth_headers)
        assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"
        run = r.json()
        assert run["status"] == "success"
        assert int(run.get("listings_seen") or 0) == 12
        # Deterministic — no new listings the 2nd time
        assert int(run.get("listings_new") or 0) == 0, f"expected 0 new, got {run.get('listings_new')}"
        assert int(run.get("listings_updated") or 0) >= 1

    def test_collect_unknown_source_404(self, client, auth_headers):
        r = client.post(f"{API}/admin/market/sources/does-not-exist/collect", headers=auth_headers)
        assert r.status_code == 404


# =====================================================================
# 3. ANALYTICS
# =====================================================================
class TestAnalytics:
    def test_source_strip(self, client, auth_headers):
        r = client.get(f"{API}/admin/market/analytics/source-strip", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        row = next((s for s in data if s["source_id"] == _state["source_id"]), None)
        assert row, "seed source missing from source-strip"
        for k in ("source_id", "name", "active", "collector", "runs",
                  "success_rate", "listings_ingested", "last_run_at", "consecutive_failures"):
            assert k in row, f"missing key {k}"
        assert row["collector"] == "seed"
        assert row["runs"] >= 2
        assert row["success_rate"] == 100.0
        assert row["listings_ingested"] >= 12

    def test_price_trends(self, client, auth_headers):
        r = client.get(f"{API}/admin/market/analytics/price-trends",
                       params={"purpose": "sale", "months": 12}, headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        if data:
            for row in data:
                assert "month" in row and "count" in row and "median" in row

    def test_median_by_suburb(self, client, auth_headers):
        r = client.get(f"{API}/admin/market/analytics/median-by-suburb",
                       params={"purpose": "sale"}, headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        # sorted desc by median
        if len(data) >= 2:
            meds = [row["median"] for row in data]
            assert meds == sorted(meds, reverse=True)
        for row in data:
            assert {"suburb", "count", "median"} <= set(row.keys())

    def test_heatmap(self, client, auth_headers):
        r = client.get(f"{API}/admin/market/analytics/heatmap",
                       params={"purpose": "sale", "months": 12}, headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert set(data.keys()) >= {"months", "suburbs", "cells"}
        assert isinstance(data["months"], list)
        assert isinstance(data["suburbs"], list)
        assert isinstance(data["cells"], list)
        if data["cells"]:
            cell0 = data["cells"][0]
            assert "suburb" in cell0

    def test_quick_insights(self, client, auth_headers):
        r = client.get(f"{API}/admin/market/analytics/quick-insights", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        for k in ("by_class", "by_purpose", "match_bands"):
            assert k in data, f"missing {k}"
            assert isinstance(data[k], list)


# =====================================================================
# 4. SCHEDULER
# =====================================================================
class TestScheduler:
    def test_get_scheduler_state(self, client, auth_headers):
        r = client.get(f"{API}/admin/market/scheduler", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        for k in ("paused", "tick_seconds", "task_running"):
            assert k in data
        assert data["task_running"] is True

    def test_pause_and_resume(self, client, auth_headers):
        r = client.post(f"{API}/admin/market/scheduler/pause",
                        json={"paused": True}, headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["paused"] is True
        assert data["task_running"] is True

        r2 = client.post(f"{API}/admin/market/scheduler/pause",
                         json={"paused": False}, headers=auth_headers)
        assert r2.status_code == 200
        assert r2.json()["paused"] is False


# =====================================================================
# 5. PUBLIC GUIDANCE (no auth)
# =====================================================================
class TestPublicGuidance:
    def _payload(self, **over):
        base = {
            "purpose": "sale",
            "property_class": "residential",
            "suburb": "Gordons",
            "workflow": "seller",
            "subject_asking_price": 900000,
        }
        base.update(over)
        return base

    def test_public_guidance_no_auth(self):
        # Explicitly no Authorization header
        r = requests.post(f"{API}/public/guidance/run", json=self._payload(),
                          headers={"Content-Type": "application/json"})
        assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"
        data = r.json()
        for k in ("workflow", "purpose", "comparable_count", "observed_range",
                  "median", "weighted_median", "trel_indicative_range",
                  "confidence_label", "confidence_score", "position", "delta_pct",
                  "algorithm_version", "config_version", "comparables_sample"):
            assert k in data, f"missing key {k}"
        assert data["workflow"] == "seller"
        assert data["purpose"] == "sale"
        assert data["algorithm_version"] == "GUIDE-1.0"
        if data["position"] is not None:
            assert data["position"] in ("BELOW", "WITHIN", "ABOVE")
        assert isinstance(data["comparables_sample"], list)

    def test_public_guidance_all_workflows(self):
        for wf in ("seller", "buyer", "landlord", "renter"):
            purpose = "rent" if wf in ("landlord", "renter") else "sale"
            p = self._payload(workflow=wf, purpose=purpose)
            r = requests.post(f"{API}/public/guidance/run", json=p,
                              headers={"Content-Type": "application/json"})
            assert r.status_code == 200, f"{wf}: {r.status_code} {r.text[:200]}"
            assert r.json()["workflow"] == wf

    def test_public_guidance_missing_suburb_400(self):
        p = self._payload()
        p.pop("suburb")
        r = requests.post(f"{API}/public/guidance/run", json=p,
                          headers={"Content-Type": "application/json"})
        assert r.status_code == 400

    def test_public_guidance_invalid_workflow_400(self):
        p = self._payload(workflow="admin")
        r = requests.post(f"{API}/public/guidance/run", json=p,
                          headers={"Content-Type": "application/json"})
        assert r.status_code == 400

    def test_public_guidance_invalid_purpose_400(self):
        p = self._payload(purpose="lease")
        r = requests.post(f"{API}/public/guidance/run", json=p,
                          headers={"Content-Type": "application/json"})
        assert r.status_code == 400


# =====================================================================
# CLEANUP
# =====================================================================
@pytest.fixture(scope="module", autouse=True)
def cleanup_module(client):
    yield
    # Restore scheduler to unpaused state
    if _state.get("token"):
        h = {"Authorization": f"Bearer {_state['token']}", "Content-Type": "application/json"}
        try:
            client.post(f"{API}/admin/market/scheduler/pause", json={"paused": False}, headers=h)
        except Exception:
            pass
        # Delete test source (cascade cleanup via direct mongo)
        try:
            import asyncio
            from motor.motor_asyncio import AsyncIOMotorClient
            mongo_url = os.environ.get("MONGO_URL")
            db_name = os.environ.get("DB_NAME")
            if mongo_url and db_name:
                async def _purge():
                    mc = AsyncIOMotorClient(mongo_url)
                    d = mc[db_name]
                    sids = [s["id"] async for s in d.market_sources.find(
                        {"name": {"$regex": "^TEST_ITER30"}}, {"id": 1})]
                    for sid in sids:
                        # collect listing ids first
                        lids = [l["id"] async for l in d.market_listings.find({"source_id": sid}, {"id": 1})]
                        await d.market_listing_snapshots.delete_many({"market_listing_id": {"$in": lids}})
                        await d.property_matches.delete_many({"market_listing_id": {"$in": lids}})
                        await d.market_listings.delete_many({"source_id": sid})
                        await d.collection_runs.delete_many({"source_id": sid})
                        await d.market_sources.delete_one({"id": sid})
                    # Remove non-backfill masters created by seed
                    await d.master_properties.delete_many(
                        {"canonical_fields.provenance": {"$ne": "trel_backfill"}})
                    await d.guidance_results.delete_many({})
                    await d.guidance_comparables.delete_many({})
                    await d.valuation_requests.delete_many({})
                    await d.market_review_cases.delete_many({})
                    mc.close()
                asyncio.new_event_loop().run_until_complete(_purge())
        except Exception as e:
            print(f"cleanup error (non-fatal): {e}")
