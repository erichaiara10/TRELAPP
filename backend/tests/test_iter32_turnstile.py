"""Iteration 32 — Cloudflare Turnstile enforcement on /auth/login and /auth/register,
plus brute-force lockout regression and /advertiser universal access."""
import os
import random
import string

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")
API = f"{BASE_URL}/api"

PASS_TOKEN = "1x0000000000000000000000000000AA"
FAIL_TOKEN = "2x0000000000000000000000000000AA"
backend_env = dotenv_values("/app/backend/.env")
ADMIN = {
    "email": os.environ.get("ADMIN_EMAIL") or backend_env.get("ADMIN_EMAIL"),
    "password": os.environ.get("ADMIN_PASSWORD") or backend_env.get("ADMIN_PASSWORD"),
}
if not ADMIN["email"] or not ADMIN["password"]:
    pytest.skip("Test-admin credentials are not configured", allow_module_level=True)


def rand_email(prefix="ephemeral"):
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
    return f"TEST_{prefix}_{suffix}@example.com".lower()


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def created_emails():
    emails = []
    yield emails
    # NOTE: import core.db here would pick up DB_NAME's "trel_db" fallback because
    # backend/.env is not loaded in the pytest process — read the env file explicitly.
    from dotenv import dotenv_values
    from pymongo import MongoClient

    backend_env = dotenv_values("/app/backend/.env")
    mongo_url = os.environ.get("MONGO_URL") or backend_env["MONGO_URL"]
    db_name = os.environ.get("DB_NAME") or backend_env["DB_NAME"]
    db = MongoClient(mongo_url)[db_name]
    for email in emails:
        user = db.users.find_one({"email": email.lower()})
        if user:
            db.advertiser_profiles.delete_many({"user_id": user["id"]})
            db.referral_partner_profiles.delete_many({"user_id": user["id"]})
            db.identity_documents.delete_many({"user_id": user["id"]})
        db.users.delete_many({"email": email.lower()})
    db.login_failures.delete_many({})


# ---- Turnstile enforcement: /auth/login ----
class TestLoginTurnstile:
    def test_login_without_token_rejected(self, client):
        r = client.post(f"{API}/auth/login", json={**ADMIN, "turnstile_token": None})
        assert r.status_code == 400, r.text
        assert "Human verification" in r.text

    def test_login_with_empty_token_rejected(self, client):
        r = client.post(f"{API}/auth/login", json={**ADMIN, "turnstile_token": ""})
        assert r.status_code == 400, r.text
        assert "Human verification" in r.text

    def test_always_pass_secret_accepts_any_token(self, client):
        """Documented behaviour: the configured secret is Cloudflare's ALWAYS-PASSING
        test secret, so /siteverify returns success for ANY non-empty response value
        (including the always-failing test token). The real reject path can only be
        exercised with a production secret."""
        r = client.post(f"{API}/auth/login", json={**ADMIN, "turnstile_token": FAIL_TOKEN})
        assert r.status_code == 200, r.text

    def test_login_with_passing_token_succeeds(self, client):
        r = client.post(f"{API}/auth/login", json={**ADMIN, "turnstile_token": PASS_TOKEN})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["email"] == ADMIN["email"]
        assert data["account_category"] == "STAFF"
        assert isinstance(data["token"], str) and len(data["token"]) > 20
        # httpOnly cookie set
        cookie_header = r.headers.get("set-cookie", "")
        assert "access_token=" in cookie_header
        assert "HttpOnly" in cookie_header or "httponly" in cookie_header

    def test_wrong_password_still_401_with_valid_token(self, client):
        r = client.post(f"{API}/auth/login",
                        json={"email": ADMIN["email"], "password": "totally-wrong", "turnstile_token": PASS_TOKEN})
        assert r.status_code == 401, r.text


# ---- Turnstile enforcement: /auth/register ----
class TestRegisterTurnstile:
    def test_register_without_token_rejected(self, client, created_emails):
        email = rand_email()
        r = client.post(f"{API}/auth/register", json={
            "name": "Test Advertiser", "email": email, "phone": "+67512345678",
            "password": "Password@123",
            "advertiser_relationship_type": "OWNER", "turnstile_token": None,
        })
        assert r.status_code == 400, r.text
        assert "Human verification" in r.text

    def test_register_advertiser_with_token_then_login(self, client, created_emails):
        email = rand_email("adv")
        created_emails.append(email)
        r = client.post(f"{API}/auth/register", json={
            "name": "Test Advertiser", "email": email, "phone": "+67512345678",
            "password": "Password@123",
            "advertiser_relationship_type": "AUTHORISED_AGENT",
            "turnstile_token": PASS_TOKEN,
        })
        assert r.status_code == 201, r.text
        assert r.json()["account_category"] == "PROPERTY_ADVERTISER"

        lr = client.post(f"{API}/auth/login",
                         json={"email": email, "password": "Password@123", "turnstile_token": PASS_TOKEN})
        assert lr.status_code == 200, lr.text
        assert lr.json()["account_category"] == "PROPERTY_ADVERTISER"
        token = lr.json()["token"]

        me = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["email"] == email
        assert "_id" not in me.json()

    def test_public_registration_cannot_choose_referral_category(self, client, created_emails):
        email = rand_email("ref")
        created_emails.append(email)
        r = client.post(f"{API}/auth/register", json={
            "name": "Test Referral", "email": email, "phone": "+67587654321",
            "password": "Password@123", "account_category": "REFERRAL_PARTNER",
            "turnstile_token": PASS_TOKEN,
        })
        assert r.status_code == 422, r.text


# ---- Brute force lockout regression ----
class TestLockout:
    def test_lockout_after_five_failures(self, client, created_emails):
        email = rand_email("lock")
        created_emails.append(email)
        reg = client.post(f"{API}/auth/register", json={
            "name": "Lock Target", "email": email, "phone": "+67511112222",
            "password": "Password@123",
            "advertiser_relationship_type": "OWNER", "turnstile_token": PASS_TOKEN,
        })
        assert reg.status_code == 201, reg.text
        statuses = []
        for _ in range(6):
            r = client.post(f"{API}/auth/login",
                            json={"email": email, "password": "wrong-pass", "turnstile_token": PASS_TOKEN})
            statuses.append(r.status_code)
        assert statuses[:5] == [401] * 5, statuses
        assert statuses[5] == 429, statuses
