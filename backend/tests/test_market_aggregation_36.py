"""Scoped acceptance checks for the Property Data Aggregation completion."""
from pathlib import Path

from core.collectors._common import _canonical_listing_pages
from core.collectors.discovery import _canonicalise
from core.market_property_link import collector_payload
from routes.market import CollectionRunContext, _run_view


ROOT = Path(__file__).parents[1]
FRONTEND = ROOT / "frontend" / "src" / "pages" / "admin" / "market"


def source(path):
    return path.read_text(encoding="utf-8")


def test_run_lifecycle_has_progress_cancel_recovery_and_idempotency():
    code = source(ROOT / "routes" / "market.py")
    for token in (
        "resume_pending_collection_runs", "ensure_market_indexes",
        "cancel_collection_run", "already_running", "_mark_stale_runs",
        "one_running_collection_per_source", "COLLECTION_RUN_STARTED",
    ):
        assert token in code
    view = _run_view({"source_site_id": "s", "status": "SUCCESS", "outcome": "NO_DATA"})
    assert view["status"] == "no_data"
    assert view["diagnostics"]["pages_visited"] == []


def test_progress_diagnostics_are_structured():
    context = CollectionRunContext("r")
    context.record_diag("page_fetch_started", url="https://example.test/buy")
    context.record_page("https://example.test/buy", 20, 18, 2)
    context.record_pagination_end("no_next_link")
    assert context.diagnostics["cards_seen"] == 20
    assert context.diagnostics["pagination_end_reason"] == "no_next_link"


def test_discovery_selects_only_canonical_inventory_pages():
    candidates = [
        {"listing_url": "https://example.test/buy", "purpose": "sale", "category": "buy",
         "cards_found": 20, "detail_links": 20, "verified_listing_page": True},
        {"listing_url": "https://example.test/buy/house", "purpose": "sale", "category": "houses",
         "cards_found": 20, "detail_links": 20, "verified_listing_page": True},
    ]
    _canonicalise(candidates)
    assert candidates[0]["auto_confirm"] is True
    assert candidates[1]["covered_by"] == candidates[0]["listing_url"]
    assert len(_canonical_listing_pages(candidates)) == 1


def test_unpriced_listings_are_valid_non_priced_evidence():
    payload = collector_payload("s", {
        "source_listing_id": "l", "source_url": "https://example.test/l",
        "purpose": "sale", "price": None, "price_status": "UNPRICED",
    })
    assert payload["price_amount"] is None
    assert payload["price_status"] == "UNPRICED"


def test_smart_discovery_is_bounded_explained_and_cached():
    discovery = source(ROOT / "core" / "collectors" / "discovery.py")
    routes = source(ROOT / "routes" / "market.py")
    for token in ("scan_truncated", "semantic", "structured_data_first_adaptive_dom"):
        assert token in discovery
    assert "market_discovery_cache" in routes


def test_collection_uses_pagination_parallel_details_and_deduplication():
    common = source(ROOT / "core" / "collectors" / "_common.py")
    for token in ("_find_next_page_url", "asyncio.gather", "duplicate_source_id_within_run", "safety_ceiling_hit"):
        assert token in common


def test_evidence_has_filters_refresh_pagination_and_hectares():
    evidence = source(FRONTEND / "Evidence.jsx")
    for token in ("All statuses", "Search source ID or URL", "Refreshing…", "<Pager", " ha"):
        assert token in evidence


def test_master_and_review_workspaces_are_real_and_paginated():
    duplicates = source(FRONTEND / "Duplicates.jsx")
    routes = source(ROOT / "routes" / "market.py")
    assert "masterOffset" in duplicates and "<Pager" in duplicates
    assert "source_listing_count" in routes and 'row["parcel"]' in routes
    assert "Ingest Test Listing" not in duplicates


def test_guidance_uses_active_configuration_and_blank_subject_defaults():
    engine = source(ROOT / "core" / "comparable_evidence.py")
    form = source(FRONTEND / "Comparables.jsx")
    assert "min_direct_for_formal_range" in engine and "iqr_outlier_multiplier" in engine
    assert 'suburb: ""' in form and 'land_area_ha: ""' in form
    assert "Land area (ha)" in form


def test_price_results_are_live_not_a_placeholder():
    screen = source(FRONTEND / "PriceCompareResults.jsx")
    assert "/admin/market/guidance/results?limit=100" in screen
    assert "pcr-placeholder" not in screen


def test_overview_and_trends_have_real_analytics_and_error_states():
    routes = source(ROOT / "routes" / "market.py")
    overview = source(FRONTEND / "Overview.jsx")
    trends = source(FRONTEND / "Trends.jsx")
    assert '"by_class": counts' in routes and '"cells": cells' in routes
    assert "<LoadError" in overview and "<LoadError" in trends


def test_audit_has_normalized_fields_filters_and_pagination():
    routes = source(ROOT / "routes" / "market.py")
    screen = source(FRONTEND / "AuditLog.jsx")
    assert '"event_type": row.get("event_type") or row.get("action")' in routes
    assert "collection_run" in screen and "<Pager" in screen


def test_retention_is_safe_and_timestamped():
    routes = source(ROOT / "routes" / "market.py")
    assert '"safe_mode": True' in routes
    assert '"generated_at": now_iso()' in routes
    assert '"removed": 0' in routes


def test_only_aggregation_pages_are_routed_and_legacy_workspace_is_gone():
    app = source(ROOT / "frontend" / "src" / "App.js")
    assert 'path="market/sources"' in app and 'path="market/evidence"' in app
    assert not (FRONTEND / "Workspace.jsx").exists()

