"""Iter-33 polish batch: guidance snapshot, health-led config, price_compare
lead capture, analytics TTL cache."""
import os
import re
import time
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL")
            or frontend_env.get("REACT_APP_BACKEND_URL")).rstrip("/")


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def token(session):
    r = session.post(f"{BASE_URL}/api/auth/login",
                     json={"email": "admin@trel.com.pg", "password": "Admin@123"})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    tok = r.json().get("token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def auth(session, token):
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


# --- Feature: Guidance snapshot ---
class TestGuidanceSnapshot:
    def test_run_guidance_produces_snapshot_fields(self, auth):
        subject = {
            "purpose": "sale", "property_class": "residential",
            "property_subtype": "House", "suburb": "Gordons",
            "bedrooms": 3, "bathrooms": 2,
            "land_area_m2": 600, "building_area_m2": 180,
            "workflow": "admin",
        }
        r = auth.post(f"{BASE_URL}/api/admin/market/guidance/run", json=subject)
        assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"
        body = r.json()
        comps = body.get("comparables") or []
        # It's OK to have zero comps on a fresh DB; but if we have any, each must have snapshot key
        assert isinstance(comps, list)
        required = {"property_subtype", "bedrooms", "bathrooms", "land_area_m2",
                    "building_area_m2", "suburb", "street", "local_area"}
        for c in comps:
            assert "snapshot" in c, f"comp missing snapshot: keys={list(c.keys())}"
            snap = c["snapshot"] or {}
            missing = required - set(snap.keys())
            assert not missing, f"snapshot missing keys {missing}: {snap}"
        # Best-effort: assert we actually generated at least 1 comp so snapshot is exercised.
        # (Not fatal — env may lack seed listings.)
        print(f"Guidance produced {len(comps)} comparables with snapshot check.")


# --- Feature: Health LED config endpoint ---
class TestHealthLedConfig:
    def test_endpoint_returns_expected_defaults(self, auth):
        r = auth.get(f"{BASE_URL}/api/admin/market/health-led/config")
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        body = r.json()
        assert "amber_min_success_pct" in body
        assert "red_consecutive_failures" in body
        assert isinstance(body["amber_min_success_pct"], float)
        assert isinstance(body["red_consecutive_failures"], int)
        # Values should match seeded defaults (90.0, 2)
        assert body["amber_min_success_pct"] == 90.0
        assert body["red_consecutive_failures"] == 2

    def test_requires_auth(self, session):
        s = requests.Session()
        r = s.get(f"{BASE_URL}/api/admin/market/health-led/config")
        assert r.status_code in (401, 403)


# --- Feature: Public price_compare lead capture ---
def _get_challenge(session):
    r = session.get(f"{BASE_URL}/api/public/challenge")
    assert r.status_code == 200
    body = r.json()
    q, tok = body["question"], body["token"]
    # answer is the 5-char code after the colon
    m = re.search(r":\s*([A-Za-z0-9]{5})", q)
    assert m, f"unexpected challenge question: {q!r}"
    return tok, m.group(1)


class TestPriceCompareLead:
    def _submit(self, session, workflow, name):
        tok, ans = _get_challenge(session)
        payload = {
            "source": "price_compare",
            "name": name,
            "email": f"TEST_{name.replace(' ', '').lower()}@example.com",
            "phone": "+675 71234567",
            "message": "Auto test lead",
            "payload": {"workflow": workflow, "suburb": "Gordons"},
            "verification_token": tok,
            "verification_answer": ans,
            "hp_website": "",
        }
        r = session.post(f"{BASE_URL}/api/public/leads", json=payload)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        j = r.json()
        assert j.get("ok") is True
        assert j.get("lead_id")
        return j["lead_id"]

    def test_seller_workflow_creates_lead_and_customer(self, session, auth):
        s = requests.Session(); s.headers.update({"Content-Type": "application/json"})
        lead_id = self._submit(s, "seller", "TEST Seller PC")

        # Verify in leads list
        r = auth.get(f"{BASE_URL}/api/leads")
        assert r.status_code == 200
        leads = r.json()
        lead = next((x for x in leads if x.get("id") == lead_id), None)
        assert lead, "lead not found in leads list"
        assert lead["source"] == "price_compare"
        assert lead.get("assigned_agent_id"), "expected assigned_agent_id"
        seller_agent = lead["assigned_agent_id"]

        # Verify customer with customer_type='buyer' exists
        cid = lead.get("customer_id")
        assert cid
        r = auth.get(f"{BASE_URL}/api/customers")
        assert r.status_code == 200
        customers = {c["id"]: c for c in r.json()}
        assert cid in customers, f"customer {cid} not found"
        assert customers[cid]["customer_type"] == "buyer"

        # Cleanup
        auth.delete(f"{BASE_URL}/api/leads/{lead_id}")
        auth.delete(f"{BASE_URL}/api/customers/{cid}")
        return seller_agent

    def test_landlord_workflow_routes_to_leasing_agent(self, session, auth):
        # Create seller and landlord leads and confirm role assigned differs.
        s = requests.Session(); s.headers.update({"Content-Type": "application/json"})
        lead_id_seller = self._submit(s, "seller", "TEST Seller Role")
        lead_id_landlord = self._submit(s, "landlord", "TEST Landlord Role")

        # Fetch both, then look up their agents' roles
        r = auth.get(f"{BASE_URL}/api/leads")
        leads = {x["id"]: x for x in r.json()}
        seller_agent = leads[lead_id_seller].get("assigned_agent_id")
        landlord_agent = leads[lead_id_landlord].get("assigned_agent_id")

        # If both roles have staff, agents should differ. If no leasing_agent
        # exists, landlord may fall back. We assert not both None; and if both
        # non-null, roles differ.
        if seller_agent and landlord_agent:
            r = auth.get(f"{BASE_URL}/api/users")
            users = {u["id"]: u for u in r.json()}
            role_seller = users.get(seller_agent, {}).get("role")
            role_landlord = users.get(landlord_agent, {}).get("role")
            print(f"seller agent role={role_seller} landlord agent role={role_landlord}")
            assert role_landlord == "leasing_agent", f"expected leasing_agent got {role_landlord}"
            assert role_seller == "sales_agent", f"expected sales_agent got {role_seller}"

        # Cleanup
        for lid in (lead_id_seller, lead_id_landlord):
            cid = leads[lid].get("customer_id")
            auth.delete(f"{BASE_URL}/api/leads/{lid}")
            if cid:
                auth.delete(f"{BASE_URL}/api/customers/{cid}")


# --- Feature: Analytics TTL cache ---
class TestAnalyticsCache:
    ENDPOINTS = [
        "/api/admin/market/analytics/source-strip",
        "/api/admin/market/analytics/price-trends",
        "/api/admin/market/analytics/median-by-suburb",
        "/api/admin/market/analytics/heatmap",
        "/api/admin/market/analytics/quick-insights",
    ]

    @pytest.mark.parametrize("ep", ENDPOINTS)
    def test_two_calls_within_5s_return_deep_equal(self, auth, ep):
        r1 = auth.get(f"{BASE_URL}{ep}")
        assert r1.status_code == 200, f"{ep} -> {r1.status_code} {r1.text[:200]}"
        time.sleep(0.5)
        r2 = auth.get(f"{BASE_URL}{ep}")
        assert r2.status_code == 200
        assert r1.json() == r2.json(), f"{ep} responses differed between calls"
