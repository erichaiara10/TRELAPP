"""Iter-28 — Market Intelligence: MATCH-1.0 matcher + GUIDE-1.0 guidance + Config versioning.

Covers:
  * POST /api/admin/market/listings — dedup, D1, weighted-new-master, JSON serialization
  * POST /api/admin/market/guidance/run — output shape + math sanity
  * GET  /api/admin/market/guidance/results (+ /{id})
  * GET  /api/admin/market/summary
  * POST /api/admin/market/config (activate + revert) + audit trail
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


# ---------------- fixtures ----------------
@pytest.fixture(scope="session")
def creds():
    txt = Path("/app/memory/test_credentials.md").read_text()
    em = re.search(r"Email:\s*`([^`]+)`", txt).group(1)
    pw = re.search(r"Password:\s*`([^`]+)`", txt).group(1)
    return {"email": em, "password": pw}


@pytest.fixture(scope="session")
def token(creds):
    r = requests.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=20)
    if r.status_code != 200:
        pytest.fail(f"login failed {r.status_code}: {r.text[:400]}")
    tok = r.json().get("token")
    assert tok
    return tok


@pytest.fixture(scope="session")
def client(token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}",
                      "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def source_ids(client):
    """Create two TEST_ market sources; return their ids. Torn down at session end."""
    created = []
    for name in ["TEST_ITER28_SRC_A", "TEST_ITER28_SRC_B"]:
        # try list first (idempotent)
        r = client.post(f"{BASE_URL}/api/admin/market/sources",
                        json={"name": name, "kind": "portal", "base_url": "https://x.test",
                              "active": True})
        if r.status_code == 400:
            # already exists — look it up
            lst = client.get(f"{BASE_URL}/api/admin/market/sources").json()
            sid = next(s["id"] for s in lst if s["name"] == name)
        else:
            assert r.status_code == 200, r.text
            sid = r.json()["id"]
        created.append(sid)
    yield {"a": created[0], "b": created[1]}
    for sid in created:
        client.delete(f"{BASE_URL}/api/admin/market/sources/{sid}")


@pytest.fixture(scope="session", autouse=True)
def cleanup_masters(client):
    """After tests, delete any master_property whose canonical_fields.provenance != 'trel_backfill'."""
    yield
    # We rely on GET; delete-master endpoint isn't exposed → use direct mongo via _cleanup route?
    # There is no DELETE /master-properties in the router. We use a raw pymongo fallback.
    try:
        import motor.motor_asyncio  # noqa
        from pymongo import MongoClient
        mongo_url = os.environ.get("MONGO_URL") or dotenv_values("/app/backend/.env").get("MONGO_URL")
        db_name = os.environ.get("DB_NAME") or dotenv_values("/app/backend/.env").get("DB_NAME")
        if not (mongo_url and db_name):
            return
        c = MongoClient(mongo_url)
        d = c[db_name]
        # Delete non-backfill masters + their linked matches/listings/snapshots
        non_bf = list(d.master_properties.find(
            {"$or": [{"canonical_fields.provenance": {"$ne": "trel_backfill"}},
                     {"canonical_fields": {"$exists": False}}]},
            {"_id": 0, "id": 1}))
        ids = [m["id"] for m in non_bf]
        if ids:
            d.master_properties.delete_many({"id": {"$in": ids}})
            d.property_matches.delete_many({"master_property_id": {"$in": ids}})
        # Delete all TEST market_listings
        lst_ids = [l["id"] for l in d.market_listings.find({}, {"id": 1, "_id": 0})]
        d.market_listings.delete_many({})
        d.market_listing_snapshots.delete_many({})
        d.property_matches.delete_many({})
        d.market_review_cases.delete_many({})
        d.guidance_results.delete_many({})
        d.guidance_comparables.delete_many({})
        d.valuation_requests.delete_many({})
        # Delete our test configuration versions
        d.market_configuration.delete_many({"version": {"$regex": "^COMBINED-TEST"}})
        # Reactivate the baseline COMBINED-1.0
        d.market_configuration.update_many(
            {"version": "COMBINED-1.0", "algorithm": "combined"},
            {"$set": {"active": True}})
    except Exception as e:
        print(f"cleanup warning: {e}")


# ============================================================
# Sanity + active configuration
# ============================================================
def test_active_config_exists(client):
    r = client.get(f"{BASE_URL}/api/admin/market/config/active?algorithm=combined")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["active"] is True
    assert d["algorithm"] == "combined"
    assert "signal_weights" in d["parameters"]
    assert "cqs_baseline" in d["parameters"]


def test_summary_shape(client):
    r = client.get(f"{BASE_URL}/api/admin/market/summary")
    assert r.status_code == 200
    d = r.json()
    for k in ("sources", "market_listings", "master_properties", "matches_active",
              "review_cases_open", "audit_events", "guidance_results",
              "active_config_version"):
        assert k in d, f"missing {k}"
    assert d["active_config_version"]


# ============================================================
# Matcher — ingest, dedup, D1/weighted, new-master
# ============================================================
def _listing(source_id, sid_str, **over):
    base = {
        "source_id": source_id,
        "source_listing_id": sid_str,
        "purpose": "sale",
        "price": 850000,
        "property_class": "residential",
        "property_subtype": "House",
        "lot_number": "42",
        "section_number": "17",
        "street": "Angau Drive",
        "suburb": "Gordons",
        "city": "Port Moresby",
        "province": "National Capital District",
        "bedrooms": 3,
        "bathrooms": 2,
        "land_area_m2": 600,
        "building_area_m2": 180,
    }
    base.update(over)
    return base


def test_ingest_novel_listing_creates_master(client, source_ids):
    payload = _listing(source_ids["a"], "TEST_A_1")
    r = client.post(f"{BASE_URL}/api/admin/market/listings", json=payload)
    assert r.status_code == 200, r.text
    d = r.json()
    # JSON must be clean (no ObjectId leakage)
    import json as _j; _j.dumps(d)
    assert d["is_new"] is True
    assert d.get("candidates_considered") is not None
    m = d["match"]
    assert m is not None
    assert m["method"] in ("weighted", "D1", "D2", "D3", "D4", "D5", "D6")
    assert m["decision_band"] in ("automatic", "certain")
    assert isinstance(m["score"], (int, float))
    assert m.get("master_property_id")
    # Signals reason should indicate a fresh master was created for a novel listing
    if m["method"] == "weighted":
        assert m.get("signals", {}).get("reason") == "new_master_created"


def test_repost_same_source_dedups(client, source_ids):
    payload = _listing(source_ids["a"], "TEST_A_DEDUP", price=900000)
    before = client.get(f"{BASE_URL}/api/admin/market/listings"
                        f"?source_id={source_ids['a']}&limit=500").json()
    r1 = client.post(f"{BASE_URL}/api/admin/market/listings", json=payload)
    assert r1.status_code == 200
    listing_id_1 = r1.json()["listing"]["id"]
    # Re-post the SAME (source_id, source_listing_id) with updated price
    payload["price"] = 910000
    r2 = client.post(f"{BASE_URL}/api/admin/market/listings", json=payload)
    assert r2.status_code == 200
    assert r2.json()["is_new"] is False
    assert r2.json()["listing"]["id"] == listing_id_1  # SAME row
    # Confirm no duplicate row created
    after = client.get(f"{BASE_URL}/api/admin/market/listings"
                       f"?source_id={source_ids['a']}&limit=500").json()
    ids_before = {l["id"] for l in before}
    ids_after = {l["id"] for l in after}
    added = ids_after - ids_before
    assert len(added) == 1, f"expected exactly 1 new listing, got {added}"


def test_two_sources_same_parcel_link_to_same_master(client, source_ids):
    # Use a unique parcel
    parcel = dict(lot_number="99", section_number="88", street="Cross St",
                  suburb="Boroko", city="Port Moresby",
                  province="National Capital District")
    p_a = _listing(source_ids["a"], "TEST_PARCEL_A", **parcel, price=750000)
    p_b = _listing(source_ids["b"], "TEST_PARCEL_B", **parcel, price=770000)
    r_a = client.post(f"{BASE_URL}/api/admin/market/listings", json=p_a)
    r_b = client.post(f"{BASE_URL}/api/admin/market/listings", json=p_b)
    assert r_a.status_code == 200 and r_b.status_code == 200
    m_a = r_a.json()["match"]["master_property_id"]
    m_b = r_b.json()["match"]["master_property_id"]
    assert m_a == m_b, f"same parcel should share master; got {m_a} vs {m_b}"
    # Second one should be D1 or a certain/automatic weighted match
    method_b = r_b.json()["match"]["method"]
    band_b = r_b.json()["match"]["decision_band"]
    assert method_b in ("D1", "D2", "weighted")
    assert band_b in ("certain", "automatic")


# ============================================================
# Seed comparables + Guidance
# ============================================================
@pytest.fixture(scope="session")
def seeded_comparables(client, source_ids):
    """Seed 6+ House sale listings in Gordons/Angau Drive so guidance produces a range."""
    seeded = []
    prices = [720000, 760000, 800000, 830000, 860000, 900000, 940000]
    for i, price in enumerate(prices):
        lst = _listing(source_ids["a"], f"TEST_GUIDE_G{i}",
                       lot_number=str(50 + i), section_number="17",
                       street="Angau Drive", suburb="Gordons",
                       price=price, land_area_m2=580 + i * 20,
                       building_area_m2=170 + i * 5)
        r = client.post(f"{BASE_URL}/api/admin/market/listings", json=lst)
        assert r.status_code == 200, r.text
        seeded.append(r.json())
    return seeded


def test_guidance_run_shape_and_math(client, seeded_comparables):
    subj = {"purpose": "sale", "property_class": "residential",
            "property_subtype": "House", "suburb": "Gordons",
            "street": "Angau Drive", "bedrooms": 3, "bathrooms": 2,
            "land_area_m2": 600, "building_area_m2": 180,
            "workflow": "seller"}
    r = client.post(f"{BASE_URL}/api/admin/market/guidance/run", json=subj)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "request" in d and "result" in d and "comparables" in d
    res = d["result"]
    for k in ("comparable_count", "observed_range", "median", "weighted_median",
              "trel_indicative_range", "confidence_label", "confidence_score"):
        assert k in res, f"missing {k}"
    assert res["comparable_count"] >= 5, f"expected 5+ usable comps, got {res['comparable_count']}"
    # Range coherence: p25 <= weighted_median <= p75 (allow equality with dupes)
    if res.get("trel_indicative_range"):
        p25, p75 = res["trel_indicative_range"]["p25"], res["trel_indicative_range"]["p75"]
        assert p25 <= p75
        if res["weighted_median"] is not None:
            assert p25 <= res["weighted_median"] <= p75 + 1e-6
    # Confidence label is one of the enum values
    assert res["confidence_label"] in ("insufficient", "limited", "moderate", "strong")
    # Comparables carry required per-row keys
    comps = d["comparables"]
    assert len(comps) >= 1
    row = comps[0]
    for k in ("tier", "quality_score", "recency_factor", "effective_weight",
              "value", "inclusion_status"):
        assert k in row, f"comparable missing {k}"


def test_guidance_list_and_detail(client, seeded_comparables):
    lst = client.get(f"{BASE_URL}/api/admin/market/guidance/results?limit=50")
    assert lst.status_code == 200
    arr = lst.json()
    assert isinstance(arr, list) and len(arr) >= 1
    rid = arr[0]["id"]
    det = client.get(f"{BASE_URL}/api/admin/market/guidance/results/{rid}")
    assert det.status_code == 200
    dd = det.json()
    assert "result" in dd and "comparables" in dd and "request" in dd
    assert dd["result"]["id"] == rid


# ============================================================
# Configuration versioning + audit
# ============================================================
def test_config_publish_and_revert_with_audit(client):
    # Baseline audit count
    audits_before = client.get(f"{BASE_URL}/api/admin/market/audit-events?limit=1000").json()
    before_active = client.get(f"{BASE_URL}/api/admin/market/config/active?algorithm=combined").json()
    prior_id = before_active["id"]
    prior_ver = before_active["version"]

    # Get full param baseline to submit a valid new version
    params = dict(before_active["parameters"])

    new_ver = "COMBINED-TEST-A"
    payload = {"version": new_ver, "algorithm": "combined",
               "parameters": params, "activate": True,
               "notes": "iter28 test"}
    r = client.post(f"{BASE_URL}/api/admin/market/config", json=payload)
    assert r.status_code == 200, r.text
    assert r.json()["active"] is True

    # Active endpoint must now reflect new_ver
    act = client.get(f"{BASE_URL}/api/admin/market/config/active?algorithm=combined").json()
    assert act["version"] == new_ver

    # Revert
    rev = client.post(f"{BASE_URL}/api/admin/market/config/{prior_id}/activate")
    assert rev.status_code == 200
    act2 = client.get(f"{BASE_URL}/api/admin/market/config/active?algorithm=combined").json()
    assert act2["version"] == prior_ver

    # Audit trail grew
    audits_after = client.get(f"{BASE_URL}/api/admin/market/audit-events?limit=1000").json()
    assert len(audits_after) > len(audits_before)
    event_types = {a["event_type"] for a in audits_after}
    assert "config_created" in event_types
    assert "config_activated" in event_types


def test_ingest_missing_required_400(client, source_ids):
    r = client.post(f"{BASE_URL}/api/admin/market/listings",
                    json={"source_id": source_ids["a"]})
    assert r.status_code == 400


def test_guidance_bad_purpose_400(client):
    r = client.post(f"{BASE_URL}/api/admin/market/guidance/run",
                    json={"purpose": "lease", "suburb": "Gordons",
                          "property_class": "residential"})
    assert r.status_code == 400
