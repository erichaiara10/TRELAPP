from fastapi import FastAPI
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

from core.security import get_current_user
from routes import advertiser


def test_draft_api_saves_fields_and_keeps_accounts_separate(monkeypatch):
    monkeypatch.setattr(advertiser, "db", AsyncMongoMockClient()["trel_test"])
    user = {"id": "advertiser-a", "account_category": "PROPERTY_ADVERTISER", "status": "ACTIVE"}
    app = FastAPI()
    app.include_router(advertiser.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: user
    endpoint = "/api/property-advertising/advertiser/drafts/current"
    payload = {"data": {"listing_type": "Rent", "service": "Advertise only",
                        "relationship": "Authorised Real Estate Agent",
                        "title": "Private recovery test", "description": "Controlled test draft",
                        "price": "2800", "province": "NCD", "city": "Port Moresby",
                        "section": "42", "lot": "15", "bedrooms": "3"}, "current_step": 3}
    with TestClient(app) as c:
        assert c.put(endpoint, json=payload).status_code == 200
        saved = c.get(endpoint).json()
        assert saved["data"] == payload["data"]
        assert saved["current_step"] == 3
        user["id"] = "advertiser-b"
        assert c.get(endpoint).json() == {"data": {}, "current_step": 1}
        user["account_category"] = "STAFF"
        assert c.put(endpoint, json=payload).status_code == 403
