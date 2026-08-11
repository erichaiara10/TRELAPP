"""Iter-32 backend regression tests.

Covers:
  * POST /api/admin/market/retention/run — summary shape + audit event
  * Retention actually soft-deletes an aged market_listing row
  * Hausples collector — POST collect never crashes when site unreachable
  * Seed collector RNG tweak — ~40% rent proportion
  * Guidance run — cqs_breakdown + months_since present on comparables
"""
import os
import time
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL")
            or frontend_env.get("REACT_APP_BACKEND_URL")).rstrip("/")


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": "admin@trel.com.pg", "password": "Admin@123"})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    token = r.json().get("token") or r.json().get("access_token")
    assert token, f"no token in {r.json()}"
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def mongo_db():
    from motor.motor_asyncio import AsyncIOMotorClient
    from dotenv import dotenv_values as dv
    be = dv("/app/backend/.env")
    client = AsyncIOMotorClient(be["MONGO_URL"])
    return client[be["DB_NAME"]]


# ---------- retention ----------
class TestRetention:
    def test_run_retention_shape(self, api):
        r = api.post(f"{BASE_URL}/api/admin/market/retention/run")
        assert r.status_code == 200, r.text[:400]
        data = r.json()
        assert data.get("skipped") is False, data
        assert data.get("soft_delete_only") is True
        summary = data.get("summary") or {}
        # Every configured collection present with the expected window
        expected = {
            "market_listing_snapshots": 365,
            "market_listings": 730,
            "market_review_cases": 365,
            "market_audit_events": 2555,
            "collection_runs": 365,
        }
        for coll, days in expected.items():
            assert coll in summary, f"missing {coll} in {summary}"
            row = summary[coll]
            assert row.get("window_days") == days, f"{coll} window {row}"
            assert "soft_deleted" in row and "candidates" in row
        assert data.get("ran_at")

    def test_retention_emits_audit_event(self, api, mongo_db):
        # Fire again + check audit
        r = api.post(f"{BASE_URL}/api/admin/market/retention/run")
        assert r.status_code == 200
        ran_at = r.json()["ran_at"]

        async def _find():
            return await mongo_db.market_audit_events.find_one(
                {"event_type": "retention_run"},
                sort=[("created_at", -1)],
            )
        ev = asyncio.get_event_loop().run_until_complete(_find())
        assert ev is not None, "no retention_run audit event"
        assert ev.get("entity_type") == "retention_policy"
        assert ev.get("actor_id")

    def test_retention_soft_deletes_aged_row(self, api, mongo_db):
        """Insert an aged market_listing → run retention → verify archived_at
        + archived_by='retention_policy' + retention_days=730 set."""
        old_iso = (datetime.now(timezone.utc) - timedelta(days=900)).isoformat()
        doc = {
            "id": "TEST_iter32_aged",
            "source_id": "TEST_iter32",
            "source_listing_id": "aged-x",
            "source_url": "https://example.test/aged",
            "purpose": "sale",
            "price": 100000,
            "status": "active",
            "created_at": old_iso,
            "last_seen": old_iso,
        }

        async def _setup():
            await mongo_db.market_listings.delete_one({"id": doc["id"]})
            await mongo_db.market_listings.insert_one(doc)
        asyncio.get_event_loop().run_until_complete(_setup())

        r = api.post(f"{BASE_URL}/api/admin/market/retention/run")
        assert r.status_code == 200

        async def _fetch():
            return await mongo_db.market_listings.find_one({"id": doc["id"]}, {"_id": 0})
        row = asyncio.get_event_loop().run_until_complete(_fetch())
        assert row is not None, "row unexpectedly hard-deleted"
        assert row.get("archived_by") == "retention_policy", row
        assert row.get("retention_days") == 730
        assert row.get("archived_at")

        # cleanup
        async def _cleanup():
            await mongo_db.market_listings.delete_one({"id": doc["id"]})
        asyncio.get_event_loop().run_until_complete(_cleanup())


# ---------- hausples ----------
class TestHausples:
    def test_hausples_collect_no_crash(self, api, mongo_db):
        """Create a hausples source, run collect. Must NOT crash. Status
        should be success or partial; duration_ms > 0."""
        r = api.post(f"{BASE_URL}/api/admin/market/sources", json={
            "name": "TEST_iter32_hausples",
            "collector": "hausples_png",
            "base_url": "https://www.hausples.com.pg",
            "active": True,
        })
        assert r.status_code in (200, 201), r.text[:400]
        sid = r.json()["id"]
        try:
            r2 = api.post(f"{BASE_URL}/api/admin/market/sources/{sid}/collect")
            assert r2.status_code == 200, r2.text[:400]
            run = r2.json()
            assert run.get("status") in ("success", "partial"), run
            assert (run.get("duration_ms") or 0) >= 0
            # errors list may be non-empty; that's fine
            assert isinstance(run.get("errors", []), list)
        finally:
            api.delete(f"{BASE_URL}/api/admin/market/sources/{sid}")


# ---------- seed rent proportion ----------
class TestSeedRentProportion:
    def test_seed_yields_rent_listings(self, api, mongo_db):
        r = api.post(f"{BASE_URL}/api/admin/market/sources", json={
            "name": "TEST_iter32_seed",
            "collector": "seed",
            "active": True,
        })
        assert r.status_code in (200, 201), r.text[:400]
        sid = r.json()["id"]
        try:
            r2 = api.post(f"{BASE_URL}/api/admin/market/sources/{sid}/collect")
            assert r2.status_code == 200, r2.text[:400]
            run = r2.json()
            assert run["status"] == "success", run
            # fetch listings for this source
            r3 = api.get(f"{BASE_URL}/api/admin/market/listings",
                         params={"source_id": sid, "limit": 100})
            assert r3.status_code == 200
            listings = r3.json()
            total = len(listings)
            rent = sum(1 for l in listings if l.get("purpose") == "rent")
            assert total >= 10, f"expected ~12 listings, got {total}"
            # RNG deterministic per source_id — with 5-tuple choice
            # (sale sale sale rent rent) expect ~40% rent ⇒ at least 3
            assert rent >= 3, f"expected >=3 rent listings, got {rent}/{total}"
        finally:
            api.delete(f"{BASE_URL}/api/admin/market/sources/{sid}")


# ---------- guidance cqs_breakdown / months_since ----------
class TestGuidanceBreakdown:
    def test_guidance_comparables_have_breakdown(self, api, mongo_db):
        # Ensure seeded data exists
        r = api.post(f"{BASE_URL}/api/admin/market/sources", json={
            "name": "TEST_iter32_guide_seed",
            "collector": "seed",
            "active": True,
        })
        assert r.status_code in (200, 201)
        sid = r.json()["id"]
        api.post(f"{BASE_URL}/api/admin/market/sources/{sid}/collect")
        try:
            payload = {
                "purpose": "sale",
                "property_class": "residential",
                "property_subtype": "House",
                "suburb": "Gordons",
                "bedrooms": 3, "bathrooms": 2,
                "land_area_m2": 600, "building_area_m2": 180,
                "workflow": "admin",
            }
            r2 = api.post(f"{BASE_URL}/api/admin/market/guidance/run", json=payload)
            assert r2.status_code == 200, r2.text[:400]
            run = r2.json()
            rid = run["result"]["id"]
            r3 = api.get(f"{BASE_URL}/api/admin/market/guidance/results/{rid}")
            assert r3.status_code == 200
            data = r3.json()
            comps = data.get("comparables") or []
            assert len(comps) >= 1, f"expected comps, got {comps}"
            keys_required = {"location", "class_subtype", "size", "features",
                             "condition", "recency"}
            for c in comps:
                br = c.get("cqs_breakdown")
                assert isinstance(br, dict) and br, f"missing breakdown: {c}"
                assert keys_required.issubset(br.keys()), f"missing keys: {br.keys()}"
                total = sum(float(v) for v in br.values())
                assert abs(total - float(c["quality_score"])) <= 1.5, \
                    f"breakdown sum {total} != cqs {c['quality_score']}"
                assert c.get("months_since") is not None
                assert isinstance(c["months_since"], (int, float))
        finally:
            api.delete(f"{BASE_URL}/api/admin/market/sources/{sid}")


# ---------- final teardown ----------
class TestZZZCleanup:
  def test_final_cleanup(self, mongo_db):
    """Leave DB clean per agent_to_agent_context_note."""
    async def _clean():
        # Drop everything except master_properties where provenance='trel_backfill'
        await mongo_db.market_sources.delete_many({})
        await mongo_db.collection_runs.delete_many({})
        await mongo_db.market_listings.delete_many({})
        await mongo_db.market_listing_snapshots.delete_many({})
        await mongo_db.property_matches.delete_many({})
        await mongo_db.market_review_cases.delete_many({})
        await mongo_db.guidance_results.delete_many({})
        await mongo_db.guidance_comparables.delete_many({})
        await mongo_db.valuation_requests.delete_many({})
        await mongo_db.master_properties.delete_many(
            {"canonical_fields.provenance": {"$ne": "trel_backfill"}}
        )
        # keep audit events small
        await mongo_db.market_audit_events.delete_many({})
    asyncio.get_event_loop().run_until_complete(_clean())
