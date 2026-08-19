"""Tests for P1: must-change-password enforcement on first login.

Covers the security requirements from the P1 spec:
  * Wrong temp password rejected (401, generic error)
  * Correct temp password returns password_change_required + short-lived
    single-purpose token, NOT a normal access token
  * The single-purpose token cannot be used against ordinary APIs
  * Weak / mismatched / temp-reuse new passwords are rejected
  * Valid new password succeeds; must_change_password flag is cleared;
    the single-purpose token is single-use (replay rejected)
  * After success the temp password no longer works and the new password
    issues a normal access token
  * An audit event is created without password or token in metadata
"""
import asyncio
import os
import sys
import uuid

import bcrypt
import httpx
import pytest

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_database")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.db import db  # noqa: E402

API = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001") + "/api"


@pytest.fixture
def temp_password():
    # Meets strength rules but we won't reuse it as the "new" password.
    return f"Temp!Pass{uuid.uuid4().hex[:6]}Z9"


@pytest.fixture
def strong_new_password():
    return f"NewStrong#{uuid.uuid4().hex[:8]}Aa1"


@pytest.fixture
def dev_user(temp_password):
    """Create an isolated dev user with must_change_password=true, then clean up."""
    email = f"testadv.{uuid.uuid4().hex[:8]}@example.com"
    user_id = uuid.uuid4().hex
    doc = {
        "id": user_id,
        "email": email,
        "name": "Test Advertiser",
        "role": "property_advertiser",
        "password_hash": bcrypt.hashpw(temp_password.encode(), bcrypt.gensalt()).decode(),
        "must_change_password": True,
        "created_at": "2026-08-19T00:00:00+00:00",
    }

    async def _setup():
        await db.users.insert_one(doc)

    async def _teardown():
        await db.users.delete_one({"id": user_id})
        await db.used_password_change_tokens.delete_many({"user_id": user_id})
        await db.pa_audit.delete_many({"reference": user_id})

    asyncio.get_event_loop().run_until_complete(_setup())
    yield {"email": email, "user_id": user_id, "password": temp_password}
    asyncio.get_event_loop().run_until_complete(_teardown())


def _login(client, email, password):
    return client.post(f"{API}/auth/login", json={"email": email, "password": password})


def test_wrong_temp_password_rejected(dev_user):
    with httpx.Client(timeout=15) as c:
        r = _login(c, dev_user["email"], "definitely-wrong-pass")
    assert r.status_code == 401
    assert r.json()["detail"].lower().startswith("invalid")


def test_correct_temp_password_returns_challenge(dev_user):
    with httpx.Client(timeout=15) as c:
        r = _login(c, dev_user["email"], dev_user["password"])
    assert r.status_code == 200
    data = r.json()
    assert data["password_change_required"] is True
    assert data["purpose"] == "first_login_password_change"
    assert "change_token" in data and data["change_token"]
    assert "token" not in data  # no access token issued
    assert data["expires_in_seconds"] == 600


def test_change_token_denies_ordinary_apis(dev_user):
    with httpx.Client(timeout=15) as c:
        r = _login(c, dev_user["email"], dev_user["password"])
        change_token = r.json()["change_token"]
        headers = {"Authorization": f"Bearer {change_token}"}
        assert c.get(f"{API}/auth/me", headers=headers).status_code == 401
        assert c.get(f"{API}/property-advertising/workspace", headers=headers).status_code == 401


def test_weak_new_password_rejected(dev_user):
    with httpx.Client(timeout=15) as c:
        r = _login(c, dev_user["email"], dev_user["password"])
        token = r.json()["change_token"]
        for weak in ["short", "alllowercase1!", "ALLUPPER1!AAA", "NoDigits!AaaaA"]:
            resp = c.post(
                f"{API}/auth/change-password-first-login",
                json={"token": token, "new_password": weak, "confirm_password": weak},
            )
            assert resp.status_code == 400, weak


def test_mismatched_new_and_confirm_rejected(dev_user):
    with httpx.Client(timeout=15) as c:
        r = _login(c, dev_user["email"], dev_user["password"])
        token = r.json()["change_token"]
        resp = c.post(
            f"{API}/auth/change-password-first-login",
            json={"token": token, "new_password": "GoodStrong#Pass1", "confirm_password": "OtherStrong#Pass1"},
        )
        assert resp.status_code == 400
        assert "match" in resp.json()["detail"].lower()


def test_reuse_of_temp_password_rejected(dev_user):
    with httpx.Client(timeout=15) as c:
        r = _login(c, dev_user["email"], dev_user["password"])
        token = r.json()["change_token"]
        resp = c.post(
            f"{API}/auth/change-password-first-login",
            json={"token": token, "new_password": dev_user["password"], "confirm_password": dev_user["password"]},
        )
        assert resp.status_code == 400
        assert "different" in resp.json()["detail"].lower()


def test_successful_change_and_replay_and_relogin(dev_user, strong_new_password):
    async def _get_flag():
        u = await db.users.find_one({"id": dev_user["user_id"]})
        return u.get("must_change_password"), u.get("password_version")

    with httpx.Client(timeout=15) as c:
        r = _login(c, dev_user["email"], dev_user["password"])
        token = r.json()["change_token"]

        # 1. Successful change
        ok = c.post(
            f"{API}/auth/change-password-first-login",
            json={"token": token, "new_password": strong_new_password, "confirm_password": strong_new_password},
        )
        assert ok.status_code == 200
        assert ok.json()["ok"] is True

        # 2. Replay same token → rejected
        replay = c.post(
            f"{API}/auth/change-password-first-login",
            json={"token": token, "new_password": strong_new_password + "X", "confirm_password": strong_new_password + "X"},
        )
        assert replay.status_code == 400
        assert "used" in replay.json()["detail"].lower()

        # 3. Old temp password no longer works
        old = _login(c, dev_user["email"], dev_user["password"])
        assert old.status_code == 401

        # 4. New password issues a normal access token
        new = _login(c, dev_user["email"], strong_new_password)
        assert new.status_code == 200
        assert new.json().get("token")
        assert new.json().get("role") == "property_advertiser"
        assert new.json().get("password_change_required") is None

    flag, version = asyncio.get_event_loop().run_until_complete(_get_flag())
    assert flag is False
    assert version == 1


def test_audit_event_contains_no_secrets(dev_user, strong_new_password):
    with httpx.Client(timeout=15) as c:
        r = _login(c, dev_user["email"], dev_user["password"])
        token = r.json()["change_token"]
        ok = c.post(
            f"{API}/auth/change-password-first-login",
            json={"token": token, "new_password": strong_new_password, "confirm_password": strong_new_password},
        )
        assert ok.status_code == 200

    async def _fetch():
        return await db.pa_audit.find(
            {"reference": dev_user["user_id"]}
        ).to_list(20)

    events = asyncio.get_event_loop().run_until_complete(_fetch())
    assert any(e["action"] == "password_change_required_challenge_issued" for e in events)
    assert any(e["action"] == "password_changed_first_login" for e in events)
    for e in events:
        meta = e.get("metadata") or {}
        assert "password" not in meta
        assert "new_password" not in meta
        assert "token" not in meta
        # It's fine to store jti + ip.
        for k in meta:
            assert k in {"jti", "ip"}


def test_admin_login_unchanged(strong_new_password):
    """Regression — must_change_password flow does not break existing admin login."""
    with httpx.Client(timeout=15) as c:
        r = _login(c, "admin@trel.com.pg", "Admin@123")
    assert r.status_code == 200
    data = r.json()
    assert data.get("token")
    assert data.get("role") == "system_admin"
    assert data.get("password_change_required") is None
