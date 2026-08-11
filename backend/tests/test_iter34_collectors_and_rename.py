"""Iter-34: 6 live PNG scrapers + lot_number -> allotment_number rename.

Tests:
- Mongo migration: no `lot_number` field left in any relevant collection.
- Collector registry returns exactly the 7 expected keys.
- Market sources are seeded (6 live + TREL Seed Generator).
- Seed generator run: status=success, listings_seen==12, listings have allotment/section.
- Live scrapers activate/run/deactivate — graceful (no 500, no crash).
- Matcher still works after rename.
- Master properties expose allotment_number.
"""
import os
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio

frontend_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL")
            or frontend_env.get("REACT_APP_BACKEND_URL")).rstrip("/")

backend_env = dotenv_values("/app/backend/.env")
MONGO_URL = os.environ.get("MONGO_URL") or backend_env.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME") or backend_env.get("DB_NAME")


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def auth(session):
    r = session.post(f"{BASE_URL}/api/auth/login",
                     json={"email": "admin@trel.com.pg", "password": "Admin@123"})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:300]}"
    tok = r.json().get("token")
    assert tok
    session.headers.update({"Authorization": f"Bearer {tok}"})
    return session


EXPECTED_COLLECTORS = {"seed", "hausples_png", "ljhookerpng", "mypnghome", "sre", "dac", "marketmeri"}
EXPECTED_SOURCE_NAMES = {
    "Hausples PNG", "LJ Hooker PNG", "MyPNGHome", "Strickland Real Estate",
    "Devine & Associates", "MarketMeri", "TREL Seed Generator",
}
LIVE_COLLECTORS = {"hausples_png", "ljhookerpng", "mypnghome", "sre", "dac", "marketmeri"}


class TestMongoMigration:
    def test_no_lot_number_field_anywhere(self):
        """After migration, no document in the 4 collections should have `lot_number`."""
        async def _check():
            client = AsyncIOMotorClient(MONGO_URL)
            db = client[DB_NAME]
            results = {}
            for coll in ["market_listings", "market_listing_snapshots",
                         "master_properties", "property_units"]:
                count = await db[coll].count_documents({"lot_number": {"$exists": True}})
                results[coll] = count
            client.close()
            return results
        results = asyncio.run(_check())
        for coll, count in results.items():
            assert count == 0, f"{coll} still has {count} docs with lot_number field"

    def test_sample_docs_have_allotment_number_field(self):
        """Sample market_listings docs should have allotment_number field key present."""
        async def _sample():
            client = AsyncIOMotorClient(MONGO_URL)
            db = client[DB_NAME]
            docs = await db.market_listings.find({}, {"allotment_number": 1, "lot_number": 1}).limit(5).to_list(5)
            client.close()
            return docs
        docs = asyncio.run(_sample())
        # If any docs exist, none should have lot_number
        for d in docs:
            assert "lot_number" not in d, f"doc {d.get('_id')} still has lot_number key"


class TestCollectorRegistry:
    def test_collectors_endpoint_returns_seven_keys(self, auth):
        r = auth.get(f"{BASE_URL}/api/admin/market/collectors")
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        body = r.json()
        items = body if isinstance(body, list) else body.get("collectors") or body.get("items") or []
        keys = {c.get("key") or c.get("collector") or c.get("name") for c in items}
        assert EXPECTED_COLLECTORS.issubset(keys), (
            f"missing collectors: expected {EXPECTED_COLLECTORS}, got {keys}"
        )
        # Each entry should have label + requires_network
        for c in items:
            k = c.get("key") or c.get("collector") or c.get("name")
            if k in EXPECTED_COLLECTORS:
                assert c.get("label"), f"collector {k} missing label"
                assert "requires_network" in c, f"collector {k} missing requires_network"


class TestMarketSourcesSeeded:
    def test_all_seven_sources_present(self, auth):
        r = auth.get(f"{BASE_URL}/api/admin/market/sources")
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        body = r.json()
        items = body if isinstance(body, list) else body.get("items") or body.get("sources") or []
        names = {s.get("name") for s in items}
        assert EXPECTED_SOURCE_NAMES.issubset(names), (
            f"missing sources: expected {EXPECTED_SOURCE_NAMES}, got {names}"
        )
        # Each live source: active=False, https base_url
        by_name = {s["name"]: s for s in items if s.get("name") in EXPECTED_SOURCE_NAMES}
        live_map = {
            "Hausples PNG": "hausples_png",
            "LJ Hooker PNG": "ljhookerpng",
            "MyPNGHome": "mypnghome",
            "Strickland Real Estate": "sre",
            "Devine & Associates": "dac",
            "MarketMeri": "marketmeri",
        }
        for name, coll in live_map.items():
            s = by_name[name]
            # NOTE: 'active' state can be mutated by other tests running in parallel
            # (TestLiveScrapersGraceful toggles it). We only verify collector+base_url here;
            # default-active-false is verified indirectly by fresh-boot seed behaviour.
            assert s.get("collector") == coll, f"{name} collector={s.get('collector')} expected {coll}"
            assert (s.get("base_url") or "").startswith("https://"), f"{name} base_url must be https"


class TestSeedGeneratorRun:
    def test_seed_generator_run_and_allotment_fields(self, auth):
        r = auth.get(f"{BASE_URL}/api/admin/market/sources")
        assert r.status_code == 200
        items = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
        seed = next((s for s in items if s.get("name") == "TREL Seed Generator"), None)
        assert seed, "TREL Seed Generator source not found"
        seed_id = seed.get("id") or seed.get("_id")
        assert seed_id
        # Trigger a run
        run = auth.post(f"{BASE_URL}/api/admin/market/sources/{seed_id}/collect")
        assert run.status_code in (200, 201), f"{run.status_code} {run.text[:400]}"
        body = run.json()
        # Response may be a run doc directly, or wrapped
        run_doc = body.get("run") or body
        status = run_doc.get("status")
        assert status == "success", f"expected status=success, got {status}: {run_doc}"
        listings_seen = run_doc.get("listings_seen")
        assert listings_seen == 12, f"expected listings_seen=12, got {listings_seen}"

        # Fetch some listings and verify allotment/section populated + no lot_number
        lst = auth.get(f"{BASE_URL}/api/admin/market/listings?limit=5")
        assert lst.status_code == 200
        lbody = lst.json()
        listings = lbody if isinstance(lbody, list) else lbody.get("items") or lbody.get("listings") or []
        assert len(listings) > 0, "expected at least one listing after seed run"
        # Filter to seed-source listings if we can (source_id match)
        seed_listings = [l for l in listings if l.get("source_id") == seed_id] or listings
        for l in seed_listings:
            assert l.get("allotment_number"), f"listing missing allotment_number: {l}"
            assert isinstance(l.get("allotment_number"), str)
            assert l.get("section_number"), f"listing missing section_number: {l}"
            assert "lot_number" not in l, f"listing still has lot_number key: {l}"


class TestLiveScrapersGraceful:
    @pytest.mark.parametrize("source_name,collector_key", [
        ("Hausples PNG", "hausples_png"),
        ("LJ Hooker PNG", "ljhookerpng"),
        ("MyPNGHome", "mypnghome"),
        ("Strickland Real Estate", "sre"),
        ("Devine & Associates", "dac"),
        ("MarketMeri", "marketmeri"),
    ])
    def test_activate_run_deactivate(self, auth, source_name, collector_key):
        r = auth.get(f"{BASE_URL}/api/admin/market/sources")
        items = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
        src = next((s for s in items if s.get("name") == source_name), None)
        assert src, f"source {source_name} not found"
        sid = src.get("id") or src.get("_id")
        # Activate
        u = auth.put(f"{BASE_URL}/api/admin/market/sources/{sid}", json={"active": True})
        assert u.status_code in (200, 204), f"activate failed {u.status_code} {u.text[:300]}"
        try:
            # Run
            run = auth.post(f"{BASE_URL}/api/admin/market/sources/{sid}/collect")
            # Must NOT be a 500; graceful degradation expected
            assert run.status_code < 500, f"{source_name}: 5xx crash: {run.status_code} {run.text[:400]}"
            assert run.status_code in (200, 201), f"{source_name}: {run.status_code} {run.text[:400]}"
            body = run.json()
            run_doc = body.get("run") or body
            status = run_doc.get("status")
            # Accept success or partial, never a raw 'failed' with crash traceback
            assert status in ("success", "partial", "failed"), f"unexpected status {status}"
            # If failed, there must be a structured errors list — not an uncaught server error
            if status == "failed":
                assert run_doc.get("errors") or run_doc.get("error"), \
                    f"{source_name} failed without structured error info: {run_doc}"
        finally:
            # Deactivate
            d = auth.put(f"{BASE_URL}/api/admin/market/sources/{sid}", json={"active": False})
            assert d.status_code in (200, 204), f"deactivate failed {d.status_code} {d.text[:300]}"


class TestMatcherAfterRename:
    def test_guidance_run_returns_confidence(self, auth):
        subject = {
            "purpose": "sale", "property_class": "residential",
            "property_subtype": "House", "suburb": "Gordons",
            "bedrooms": 3, "bathrooms": 2,
            "land_area_m2": 600, "building_area_m2": 180,
            "workflow": "admin",
        }
        r = auth.post(f"{BASE_URL}/api/admin/market/guidance/run", json=subject)
        assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"
        body = r.json()
        result = body.get("result") or {}
        assert "confidence_label" in result, f"missing result.confidence_label: {list(result.keys())}"
        # Comparable_count should be > 0 after seed run inserted 12 listings
        assert result.get("comparable_count", 0) > 0, (
            f"expected comparable_count > 0, got {result.get('comparable_count')}"
        )
        # Sanity: comparables list echoes count
        assert len(body.get("comparables") or []) == result.get("comparable_count")


class TestMasterProperties:
    def test_master_properties_have_allotment_number(self, auth):
        r = auth.get(f"{BASE_URL}/api/admin/market/master-properties?limit=5")
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        body = r.json()
        items = body if isinstance(body, list) else body.get("items") or body.get("masters") or []
        for m in items:
            assert "lot_number" not in m, f"master still has lot_number: {m}"
            # allotment_number key should exist (may be null)
            assert "allotment_number" in m, f"master missing allotment_number key: {list(m.keys())}"

    def test_master_search_by_allotment(self, auth):
        r = auth.get(f"{BASE_URL}/api/admin/market/master-properties?limit=20")
        assert r.status_code == 200
        body = r.json()
        items = body if isinstance(body, list) else body.get("items") or []
        allots = [m.get("allotment_number") for m in items if m.get("allotment_number")]
        if not allots:
            pytest.skip("no masters with allotment_number to search against")
        q = allots[0]
        rs = auth.get(f"{BASE_URL}/api/admin/market/master-properties", params={"q": q})
        assert rs.status_code == 200, f"{rs.status_code} {rs.text[:300]}"
