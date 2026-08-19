"""D1 acceptance tests for the account-scoped Property Advertiser dashboard."""
import os
import sys
import uuid

import bcrypt
import httpx
import pytest
from pymongo import MongoClient

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_database")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-value-only-used-locally")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

API = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001") + "/api"
PREFIX = "E2E-TEST-D1-20260819"
_mongo = MongoClient(os.environ["MONGO_URL"])
db = _mongo[os.environ["DB_NAME"]]


def _account(name):
    user_id = uuid.uuid4().hex
    email = f"d1-{uuid.uuid4().hex[:10]}@example.com"
    password = "E2E#Dashboard2026"
    db.users.insert_one({
        "id": user_id,
        "email": email,
        "name": name,
        "role": "property_advertiser",
        "password_hash": bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
        "must_change_password": False,
        "created_at": "2026-08-19T00:00:00+00:00",
    })
    client = httpx.Client(timeout=30)
    response = client.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    client.headers.update({"Authorization": f"Bearer {response.json()['token']}"})
    return client, user_id, email


def _cleanup(user_id):
    refs = [
        item["reference"]
        for item in db.pa_submissions.find({"owner_user_id": user_id}, {"reference": 1})
    ]
    db.users.delete_many({"id": user_id})
    db.pa_advertisers.delete_many({"owner_user_id": user_id})
    db.pa_drafts.delete_many({"owner_user_id": user_id})
    db.pa_submissions.delete_many({"owner_user_id": user_id})
    db.pa_audit.delete_many({
        "$or": [{"performed_by_id": user_id}, {"reference": {"$in": refs}}],
    })
    db.pa_notifications.delete_many({"recipient_user_id": user_id})
    db.pa_enquiries.delete_many({"owner_user_id": user_id})
    db.pa_location_requests.delete_many({"owner_user_id": user_id})


@pytest.fixture
def fresh_advertiser():
    client, user_id, email = _account(f"{PREFIX} Fresh Advertiser")
    yield client, user_id, email
    client.close()
    _cleanup(user_id)


def test_d1_fresh_dashboard_uses_real_identity_and_zero_counts(fresh_advertiser):
    client, _, email = fresh_advertiser
    response = client.get(f"{API}/property-advertising/advertiser/dashboard")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["advertiser"]["name"] == f"{PREFIX} Fresh Advertiser"
    assert body["advertiser"]["email"] == email
    assert body["metrics"] == {
        "active_listings": 0,
        "draft_listings": 0,
        "awaiting_review": 0,
        "total_enquiries": 0,
    }
    assert body["listings"] == []
    assert body["recent_activity"] == []
    assert body["inspections"] == []
    assert "Kumul Agencies" not in response.text
    assert "18" not in {str(value) for value in body["metrics"].values()}


def test_d1_saved_draft_appears_only_for_its_owner():
    first, first_id, _ = _account(f"{PREFIX} First")
    second, second_id, _ = _account(f"{PREFIX} Second")
    try:
        unique_title = f"{PREFIX} PRIVATE-{uuid.uuid4().hex[:8]}"
        payload = {
            "data": {
                "listing_type": "sale",
                "property_class": "urban_residential",
                "property_type": "House",
                "title": unique_title,
                "photo_file_ids": [],
                "document_file_ids": [],
            },
            "current_step": 2,
        }
        saved = first.put(
            f"{API}/property-advertising/advertiser/drafts/current",
            json=payload,
        )
        assert saved.status_code == 200, saved.text

        first_dashboard = first.get(
            f"{API}/property-advertising/advertiser/dashboard"
        )
        second_dashboard = second.get(
            f"{API}/property-advertising/advertiser/dashboard"
        )
        assert first_dashboard.status_code == 200
        assert second_dashboard.status_code == 200
        assert first_dashboard.json()["metrics"]["draft_listings"] == 1
        assert unique_title in [item["title"] for item in first_dashboard.json()["listings"]]
        assert unique_title not in second_dashboard.text
        assert second_dashboard.json()["metrics"]["draft_listings"] == 0
    finally:
        first.close()
        second.close()
        _cleanup(first_id)
        _cleanup(second_id)


def test_d1_metrics_and_listing_statuses_are_computed_from_owner_records(fresh_advertiser):
    client, user_id, _ = fresh_advertiser
    now = "2026-08-19T04:00:00+00:00"
    records = [
        ("Published", "Published Property"),
        ("Submitted", "Awaiting Review Property"),
        ("Changes Required", "Returned Property"),
    ]
    for status, suffix in records:
        reference = f"TREL-D1-{uuid.uuid4().hex[:8]}"
        db.pa_submissions.insert_one({
            "id": uuid.uuid4().hex,
            "reference": reference,
            "owner_user_id": user_id,
            "status": status,
            "data": {
                "title": f"{PREFIX} {suffix}",
                "listing_type": "sale",
                "suburb": "Boroko",
                "province": "NCD",
                "price": "500000",
                "photo_file_ids": [],
                "document_file_ids": [],
            },
            "created_at": now,
            "updated_at": now,
        })

    body = client.get(
        f"{API}/property-advertising/advertiser/dashboard"
    ).json()
    assert body["metrics"]["active_listings"] == 1
    assert body["metrics"]["awaiting_review"] == 1
    assert len(body["listings"]) == 3
    assert {item["status"] for item in body["listings"]} == {
        "Published", "Submitted", "Changes Required",
    }
    assert any(item["kind"] == "changes" for item in body["reminders"])
