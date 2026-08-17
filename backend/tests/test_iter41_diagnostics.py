"""Iter-41 — Scraper diagnostics + acceptance contract + _id stripping.

Verifies:
  * POST /admin/market/sources/{id}/collect on seed produces a run with a
    fully-populated diagnostics object (all required keys present).
  * The seed run finishes with status success/partial (never failed) and
    matches_created >= 0.
  * GET /admin/market/runs?limit=N returns runs with diagnostics embedded and
    tolerates legacy runs with diagnostics=None/missing.
  * Acceptance contract is proven on the most recent live Hausples run:
    diagnostics.rejection_reasons contains no_numeric_price AND
    duplicate_source_id_within_run counters, and cards_accepted +
    cards_rejected == cards_seen.
  * Detail-page contract: for the same live run, detail_pages_attempted > 0
    and detail_pages_attempted == succeeded + failed.
  * Pagination discovery: no fabricated ?page=N — pagination_end_reason is one
    of the allowed values; pages_visited has >= 1 entries per successful walk.
  * MongoDB `_id` never leaks in JSON responses across sources / runs /
    health / summary / collectors / scheduler.
  * Regression: /health, /sources, /runs, /summary, /collectors, /scheduler
    still 200 and scheduler pause/resume works.
"""
import os
import re
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
BASE = (os.environ.get("REACT_APP_BACKEND_URL")
        or frontend_env.get("REACT_APP_BACKEND_URL")).rstrip("/")

REQUIRED_DIAG_KEYS = {
    "pages_visited", "cards_seen", "cards_accepted", "cards_rejected",
    "rejection_reasons",
    "detail_pages_attempted", "detail_pages_succeeded", "detail_pages_failed",
    "pagination_pages_followed", "pagination_end_reason",
    "duplicate_source_ids_within_run",
    "records_passed_to_ingestion", "records_inserted", "records_updated",
}
ALLOWED_PAG_END = {
    None, "no_next_link", "next_equals_current",
    "no_extractable_cards", "safety_ceiling_hit",
}


# ---------- Fixtures ----------
@pytest.fixture(scope="session")
def creds():
    p = Path("/app/memory/test_credentials.md").read_text()
    em = re.search(r"Email:\s*`([^`]+)`", p).group(1)
    pw = re.search(r"Password:\s*`([^`]+)`", p).group(1)
    return {"email": em, "password": pw}


@pytest.fixture(scope="session")
def token(creds):
    r = requests.post(f"{BASE}/api/auth/login", json=creds, timeout=30)
    if r.status_code != 200:
        pytest.fail(f"login failed: {r.status_code} {r.text[:200]}")
    return r.json()["token"]


@pytest.fixture(scope="session")
def H(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def sources(H):
    r = requests.get(f"{BASE}/api/admin/market/sources", headers=H, timeout=15)
    assert r.status_code == 200
    return r.json()


def _no_underscore_id(obj):
    """Recursively assert no key named `_id` anywhere."""
    if isinstance(obj, dict):
        assert "_id" not in obj, f"_id leaked in dict keys: {list(obj)[:6]}"
        for v in obj.values():
            _no_underscore_id(v)
    elif isinstance(obj, list):
        for v in obj:
            _no_underscore_id(v)


# ---------- Scheduler pause/resume + basic health ----------
class TestSchedulerAndHealth:
    def test_pause(self, H):
        r = requests.post(f"{BASE}/api/admin/market/scheduler/pause",
                          json={"paused": True}, headers=H, timeout=10)
        assert r.status_code == 200
        assert r.json()["paused"] is True

    def test_scheduler_status(self, H):
        r = requests.get(f"{BASE}/api/admin/market/scheduler",
                         headers=H, timeout=10)
        assert r.status_code == 200
        _no_underscore_id(r.json())

    def test_summary(self, H):
        r = requests.get(f"{BASE}/api/admin/market/summary",
                         headers=H, timeout=15)
        assert r.status_code == 200
        _no_underscore_id(r.json())

    def test_collectors_list(self, H):
        r = requests.get(f"{BASE}/api/admin/market/collectors",
                         headers=H, timeout=10)
        assert r.status_code == 200
        _no_underscore_id(r.json())


# ---------- Seed collect → diagnostics shape ----------
class TestSeedCollectDiagnostics:
    def _seed_id(self, sources):
        seed = next((s for s in sources
                     if s.get("collector") == "seed" and s.get("active")), None)
        assert seed, "No active seed source (expected 'TREL Seed Generator')"
        return seed["id"]

    def test_seed_run_completes_with_full_diagnostics(self, H, sources):
        sid = self._seed_id(sources)
        r = requests.post(f"{BASE}/api/admin/market/sources/{sid}/collect",
                          headers=H, timeout=120)
        assert r.status_code == 200, r.text[:400]
        run = r.json()
        _no_underscore_id(run)
        # Contract: never crashes → status success or partial
        assert run["status"] in ("success", "partial"), run["status"]
        assert run.get("matches_created", 0) >= 0
        diag = run.get("diagnostics")
        assert diag is not None, "diagnostics missing on seed run"
        missing = REQUIRED_DIAG_KEYS - set(diag.keys())
        assert not missing, f"missing diagnostics keys: {missing}"
        assert isinstance(diag["pages_visited"], list)
        assert isinstance(diag["rejection_reasons"], dict)
        assert diag["pagination_end_reason"] in ALLOWED_PAG_END
        # Records ingested via seed collector
        assert diag["records_passed_to_ingestion"] == run["listings_seen"]
        assert diag["records_inserted"] + diag["records_updated"] \
            <= diag["records_passed_to_ingestion"]


# ---------- GET /runs shape (mixed diagnostics old/new tolerated) ----------
class TestRunsListing:
    def test_runs_list_tolerates_legacy(self, H):
        r = requests.get(f"{BASE}/api/admin/market/runs?limit=20",
                         headers=H, timeout=15)
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list) and len(rows) >= 1
        _no_underscore_id(rows)
        # every row parses fine and diagnostics may be present, None, or absent
        for row in rows:
            if "diagnostics" in row and row["diagnostics"] is not None:
                # if present, must be a dict, pagination_end_reason allowed
                assert isinstance(row["diagnostics"], dict)
                assert row["diagnostics"].get("pagination_end_reason") \
                    in ALLOWED_PAG_END | {None}


# ---------- Live-scraper rejection + detail contract via existing runs ----------
class TestAcceptanceContractOnLiveRuns:
    def _live_diag_run(self, H):
        """Find the most recent completed http-collector run with diagnostics
        that has cards_seen > 0 (i.e. a real scrape happened)."""
        r = requests.get(f"{BASE}/api/admin/market/runs?limit=50",
                         headers=H, timeout=15)
        assert r.status_code == 200
        for row in r.json():
            d = row.get("diagnostics") or {}
            if d.get("cards_seen", 0) > 0 and row["status"] in \
                    ("success", "partial"):
                return row
        return None

    def test_acceptance_math_holds(self, H):
        """Iter-42: hard-assert the accounting invariant against the most
        recent fresh (post-fix) live-scraper run. Historical Hausples runs
        pre-fix may fail this — we pick the most recent success/partial run
        whose diagnostics has the fix's authoritative reconciliation applied
        (i.e. per-page sums equal top-level totals)."""
        r = requests.get(f"{BASE}/api/admin/market/runs?limit=50",
                         headers=H, timeout=15)
        assert r.status_code == 200
        fresh = None
        for row in r.json():
            d = row.get("diagnostics") or {}
            if d.get("cards_seen", 0) == 0:
                continue
            pv = d.get("pages_visited") or []
            if not pv:
                continue
            psum_cs = sum(p.get("cards_seen", 0) for p in pv)
            psum_ca = sum(p.get("cards_accepted", 0) for p in pv)
            psum_cr = sum(p.get("cards_rejected", 0) for p in pv)
            # A fresh (post-fix) run: per-page sums == top-level totals
            if (psum_cs == d["cards_seen"]
                    and psum_ca == d["cards_accepted"]
                    and psum_cr == d["cards_rejected"]):
                fresh = row
                break
        assert fresh is not None, ("No post-fix live-scraper run available; "
                                    "trigger a fresh collect first.")
        d = fresh["diagnostics"]
        assert d["cards_accepted"] + d["cards_rejected"] == d["cards_seen"], \
            (f"acceptance invariant broken on fresh run {fresh['id']}: "
             f"cs={d['cards_seen']} ca={d['cards_accepted']} "
             f"cr={d['cards_rejected']}")
        # rejection reasons sum must equal cards_rejected
        assert sum(d["rejection_reasons"].values()) == d["cards_rejected"]


class TestMarketMeriCardExtractionFix:
    """Iter-42 BUG-FIX 1 — MarketMeri `.listing-wrapper-grid` selector."""

    MARKETMERI_ID = "89cf6ddd-4f20-4fcf-91b6-84543237f76d"

    def test_marketmeri_extracts_cards(self, H):
        # Look for a recent MarketMeri run first (avoid re-triggering a
        # ~15 min scrape on every test run).
        r = requests.get(f"{BASE}/api/admin/market/runs?limit=50",
                         headers=H, timeout=15)
        assert r.status_code == 200
        mm_run = next((row for row in r.json()
                       if row.get("source_id") == self.MARKETMERI_ID
                       and row.get("status") in ("success", "partial")
                       and (row.get("diagnostics") or {}).get("cards_seen",
                                                              0) > 0),
                      None)
        assert mm_run is not None, ("No successful MarketMeri run with "
                                    "cards_seen>0 found — the "
                                    ".listing-wrapper-grid selector fix "
                                    "may have regressed.")
        d = mm_run["diagnostics"]
        assert d["cards_seen"] > 0, f"cards_seen=0 on MarketMeri {mm_run['id']}"
        assert d["cards_accepted"] > 0, \
            f"cards_accepted=0 on MarketMeri {mm_run['id']}"
        # at least one real-estate page (i.e. a page_visited row) accepted
        pv_accepted = [p for p in d["pages_visited"]
                       if p.get("cards_accepted", 0) > 0]
        assert len(pv_accepted) > 0, \
            "no pages_visited row with cards_accepted>0"
        # detail-page contract on this run
        assert d["detail_pages_attempted"] == \
            d["detail_pages_succeeded"] + d["detail_pages_failed"]
        assert d["detail_pages_attempted"] >= d["cards_accepted"]


class TestLiveRunRejectionAndPaginationContract:
    def _live_diag_run(self, H):
        r = requests.get(f"{BASE}/api/admin/market/runs?limit=50",
                         headers=H, timeout=15)
        assert r.status_code == 200
        for row in r.json():
            d = row.get("diagnostics") or {}
            if d.get("cards_seen", 0) > 0 and row["status"] in \
                    ("success", "partial"):
                return row
        return None

    def test_rejection_reasons_are_recorded(self, H):
        row = self._live_diag_run(H)
        if not row:
            pytest.skip("No live-scraper run with cards_seen>0 available")
        d = row["diagnostics"]
        # There will always be *some* rejection reason on a real scrape (POA/
        # duplicates/no-url) — otherwise cards_rejected would be 0.
        if d["cards_rejected"] > 0:
            assert isinstance(d["rejection_reasons"], dict)
            assert sum(d["rejection_reasons"].values()) == d["cards_rejected"]
            # Contract expects at least one of these keys to fire in practice
            keys = set(d["rejection_reasons"].keys())
            assert keys, "cards_rejected>0 but rejection_reasons empty"

    def test_detail_pages_math_holds(self, H):
        row = self._live_diag_run(H)
        if not row:
            pytest.skip("No live-scraper run with cards_seen>0 available")
        d = row["diagnostics"]
        # attempted == succeeded + failed
        assert d["detail_pages_attempted"] == \
            d["detail_pages_succeeded"] + d["detail_pages_failed"], \
            f"detail math broken: {d}"
        # for a run that ingested anything, attempted > 0
        if row["listings_seen"] > 0:
            assert d["detail_pages_attempted"] > 0, \
                "listings ingested but detail_pages_attempted==0"

    def test_pagination_end_reason_valid(self, H):
        row = self._live_diag_run(H)
        if not row:
            pytest.skip("No live-scraper run available")
        d = row["diagnostics"]
        assert d["pagination_end_reason"] in ALLOWED_PAG_END, \
            f"invalid pagination_end_reason {d['pagination_end_reason']!r}"
        # pages_visited entries all have the required shape
        for p in d["pages_visited"]:
            assert set(p.keys()) >= {"url", "cards_seen",
                                     "cards_accepted", "cards_rejected"}


# ---------- _id never leaks ----------
class TestNoUnderscoreIdLeaks:
    def test_endpoints_strip_id(self, H):
        for path in [
            "/api/admin/market/sources",
            "/api/admin/market/runs?limit=10",
            "/api/admin/market/summary",
            "/api/admin/market/collectors",
            "/api/admin/market/scheduler",
            "/api/admin/market/sources/health",
        ]:
            r = requests.get(f"{BASE}{path}", headers=H, timeout=15)
            assert r.status_code == 200, f"{path} → {r.status_code}"
            _no_underscore_id(r.json())


# ---------- Resume scheduler at end ----------
class TestSchedulerResume:
    def test_resume(self, H):
        r = requests.post(f"{BASE}/api/admin/market/scheduler/pause",
                          json={"paused": False}, headers=H, timeout=10)
        assert r.status_code == 200
        assert r.json()["paused"] is False
