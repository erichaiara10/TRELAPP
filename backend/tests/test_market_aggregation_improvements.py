from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from routes.market import CollectionRunContext, _domain, _listing_pages, _normalized_base_url, _run_heartbeat_expired, _run_view, _source_view
from core.collectors.discovery import _canonicalise


def test_normalizes_source_url_and_domain():
    assert _normalized_base_url({"base_url": "hausples.com.pg/"}) == "https://hausples.com.pg"
    assert _domain({"base_url": "https://www.hausples.com.pg/"}) == "hausples.com.pg"


def test_rejects_unsupported_source_url():
    try:
        _normalized_base_url({"base_url": "ftp://example.com"})
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("unsupported scheme was accepted")


def test_listing_pages_keep_only_unique_confirmed_http_urls():
    pages = _listing_pages([
        {"listing_url": "https://example.com/buy", "category": "sale"},
        {"listing_url": "https://example.com/buy", "category": "sale"},
        {"listing_url": "javascript:alert(1)"},
        {"listing_url": "https://example.com/rent", "category": "rent"},
    ])
    assert [p["listing_url"] for p in pages] == [
        "https://example.com/buy", "https://example.com/rent"
    ]


def test_source_view_preserves_confirmed_pages_and_safe_defaults():
    source = _source_view({"id": "s1", "collector_key": "generic_web", "listing_pages": []})
    assert source["collector"] == "generic_web"
    assert source["collection_frequency"] == "manual"
    assert source["listing_pages"] == []


def test_new_run_view_exposes_diagnostics():
    run = _run_view({
        "id": "r1", "source_site_id": "s1", "status": "SUCCESS",
        "records_seen": 2, "records_ingested": 1,
        "records_matched": 1, "records_review_required": 0,
        "diagnostics": {"cards_seen": 2, "cards_accepted": 1},
    })
    assert run["status"] == "success"
    assert run["source_id"] == "s1"
    assert run["diagnostics"]["cards_seen"] == 2


def test_run_view_distinguishes_no_data_cancelled_and_stale():
    base = {"id": "r", "source_site_id": "s", "status": "SUCCESS", "records_seen": 0}
    assert _run_view({**base, "outcome": "NO_DATA"})["status"] == "no_data"
    assert _run_view({**base, "status": "FAILED", "outcome": "CANCELLED"})["status"] == "cancelled"
    assert _run_view({**base, "status": "FAILED", "outcome": "STALE"})["status"] == "stale"


def test_run_context_reports_pages_rejections_and_progress():
    run = CollectionRunContext("r1")
    run.record_diag("page_fetch_started", url="https://example.com/buy")
    assert run.diagnostics["phase"] == "FETCHING_LIST_PAGE"
    assert run.diagnostics["current_url"] == "https://example.com/buy"
    assert run.diagnostics["cards_seen"] == 0
    run.record_diag("no_numeric_price")
    run.record_diag("duplicate_source_id_within_run")
    run.record_page("https://example.com/buy?page=1", 20, 18, 2, final=True)
    run.record_pagination_end("no_next_link")
    assert run.diagnostics["cards_seen"] == 20
    assert run.diagnostics["cards_rejected"] == 2
    assert run.diagnostics["duplicate_source_ids_within_run"] == 1
    assert run.diagnostics["pagination_end_reason"] == "no_next_link"


def test_only_highest_level_verified_page_is_auto_confirmed():
    rows = [
        {"listing_url": "https://example.com/buy", "purpose": "sale",
         "category": "buy", "cards_found": 20, "detail_links": 20,
         "verified_listing_page": True, "auto_confirm": False},
        {"listing_url": "https://example.com/buy/house/port-moresby", "purpose": "sale",
         "category": "houses", "cards_found": 20, "detail_links": 20,
         "verified_listing_page": True, "auto_confirm": False},
    ]
    _canonicalise(rows)
    assert rows[0]["auto_confirm"] is True
    assert rows[1]["auto_confirm"] is False
    assert rows[1]["covered_by"] == rows[0]["listing_url"]


def test_missing_or_old_run_heartbeat_is_recoverable():
    now = datetime(2026, 8, 30, tzinfo=timezone.utc)
    assert _run_heartbeat_expired({}, now) is True
    assert _run_heartbeat_expired({"started_at": (now - timedelta(minutes=11)).isoformat()}, now) is True
    assert _run_heartbeat_expired({"heartbeat_at": (now - timedelta(minutes=1)).isoformat()}, now) is False
