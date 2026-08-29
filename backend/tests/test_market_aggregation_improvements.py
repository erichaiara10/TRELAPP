from fastapi import HTTPException

from routes.market import _domain, _listing_pages, _normalized_base_url, _run_view, _source_view


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
