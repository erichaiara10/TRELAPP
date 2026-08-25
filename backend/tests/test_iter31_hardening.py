"""Iteration 31: verify (1) email-wide brute-force lockout with rotating X-Forwarded-For,
(2) POST /api/auth/register returns login_path='/add-property?auth=login'.
Cleans up ephemeral users and clears login_failures."""
import os
import time

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")
API = f"{BASE_URL}/api"

backend_env = dotenv_values("/app/backend/.env")
MONGO_URL = os.environ.get("MONGO_URL") or backend_env.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME") or backend_env.get("DB_NAME")

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL") or backend_env.get("ADMIN_EMAIL")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD") or backend_env.get("ADMIN_PASSWORD")
if not ADMIN_EMAIL or not ADMIN_PASSWORD:
    pytest.skip("Test-admin credentials are not configured", allow_module_level=True)


@pytest.fixture(scope="module")
def mongo():
    client = MongoClient(MONGO_URL)
    yield client[DB_NAME]
    client.close()


@pytest.fixture(autouse=True)
def clear_failures(mongo):
    mongo.login_failures.delete_many({})
    yield
    mongo.login_failures.delete_many({})


class TestBruteForceEmailWide:
    """login_guard: email-wide lockout survives rotating caller IPs."""

    def test_lockout_with_rotating_forwarded_for(self, mongo):
        session = requests.Session()
        statuses = []
        for i in range(1, 6):
            r = session.post(f"{API}/auth/login",
                             json={"email": ADMIN_EMAIL, "password": f"WrongPass{i}!"},
                             headers={"X-Forwarded-For": f"10.0.0.{i}"}, timeout=30)
            statuses.append(r.status_code)
        assert statuses == [401] * 5, f"Expected five 401s, got {statuses}"

        r6 = session.post(f"{API}/auth/login",
                          json={"email": ADMIN_EMAIL, "password": "WrongPass6!"},
                          headers={"X-Forwarded-For": "10.0.0.6"}, timeout=30)
        assert r6.status_code == 429, f"6th attempt from new IP should be 429, got {r6.status_code}: {r6.text[:200]}"
        assert "Too many" in r6.json().get("detail", "")

        # even the CORRECT password is locked out while the window is open
        r7 = session.post(f"{API}/auth/login",
                          json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                          headers={"X-Forwarded-For": "10.0.0.7"}, timeout=30)
        assert r7.status_code == 429, f"Locked account should stay locked, got {r7.status_code}"

        assert mongo.login_failures.count_documents({"email": ADMIN_EMAIL}) >= 5

    def test_successful_login_resets_email_counter(self, mongo):
        session = requests.Session()
        for i in range(1, 4):
            session.post(f"{API}/auth/login",
                         json={"email": ADMIN_EMAIL, "password": "Nope!!!!"},
                         headers={"X-Forwarded-For": f"10.1.0.{i}"}, timeout=30)
        assert mongo.login_failures.count_documents({"email": ADMIN_EMAIL}) == 3
        ok = session.post(f"{API}/auth/login",
                          json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                          headers={"X-Forwarded-For": "10.1.0.99"}, timeout=30)
        assert ok.status_code == 200, ok.text[:300]
        assert ok.json()["account_category"] == "STAFF"
        assert "access_token" in ok.cookies, "httpOnly access_token cookie not set"
        assert mongo.login_failures.count_documents({"email": ADMIN_EMAIL}) == 0


class TestRegisterLoginPath:
    """POST /api/auth/register login_path must point to the popup route."""

    EXPECTED = "/add-property?auth=login"

    def _admin_token(self):
        r = requests.post(f"{API}/auth/login",
                          json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        return r.json()["token"]

    def _cleanup(self, mongo, email):
        user = mongo.users.find_one({"email": email})
        if user:
            mongo.advertiser_profiles.delete_many({"user_id": user["id"]})
            mongo.referral_partner_profiles.delete_many({"user_id": user["id"]})
            mongo.users.delete_one({"id": user["id"]})

    def test_register_returns_popup_login_path(self, mongo):
        category, relationship = "PROPERTY_ADVERTISER", "OWNER"
        stamp = int(time.time() * 1000)
        email = f"test_iter31_{category.lower()}_{stamp}@example.com"
        payload = {"name": "TEST Iter31", "email": email, "phone": "+67570000000",
                   "password": "Passw0rd!23"}
        if relationship:
            payload["advertiser_relationship_type"] = relationship
        try:
            r = requests.post(f"{API}/auth/register", json=payload, timeout=30)
            assert r.status_code == 201, r.text[:300]
            data = r.json()
            assert data["ok"] is True
            assert data["account_category"] == category
            assert data["login_path"] == self.EXPECTED, f"login_path={data['login_path']!r}"
            assert data["login_path"] != "/admin/login"

            # login works and routes to the right workspace
            login = requests.post(f"{API}/auth/login",
                                  json={"email": email, "password": "Passw0rd!23"}, timeout=30)
            assert login.status_code == 200, login.text[:300]
            body = login.json()
            assert body["account_category"] == category
            assert body["workspace_path"] == "/advertiser", body["workspace_path"]
        finally:
            self._cleanup(mongo, email)
            assert mongo.users.find_one({"email": email}) is None


class TestPasswordHashFormat:
    """bcrypt hash format sanity for the seeded admin."""

    def test_admin_hash_is_bcrypt(self, mongo):
        user = mongo.users.find_one({"email": ADMIN_EMAIL})
        assert user is not None, "seeded admin missing"
        assert user["password_hash"].startswith("$2b$"), user["password_hash"][:10]
