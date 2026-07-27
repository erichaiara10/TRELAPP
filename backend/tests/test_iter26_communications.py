"""Iteration 26 — Refactor regression + Customer Communications feature.

Covers:
- Backend refactor smoke (all major /api routes still function)
- New /api/customers/{cid}/communications GET/POST
- Backward compat /api/leads/{lid}/communications
- Legacy lead comm (no parent_type) still returned by list
- DELETE /api/communications/{cid}
- Cascade delete on customer & lead removal
"""
import os
import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")).rstrip("/")
ADMIN = {"email": "admin@trel.com.pg", "password": "Admin@123"}


@pytest.fixture(scope="module")
def headers():
    r = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "Content-Type": "application/json"}


# ----- Refactor regression smoke -----
def test_root_ok():
    r = requests.get(f"{BASE_URL}/api/", timeout=15)
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_auth_me(headers):
    r = requests.get(f"{BASE_URL}/api/auth/me", headers=headers, timeout=15)
    assert r.status_code == 200
    assert r.json().get("email") == ADMIN["email"]


@pytest.mark.parametrize("path", [
    "/api/users", "/api/properties", "/api/property-types",
    "/api/customers", "/api/requirements", "/api/leads",
    "/api/inspections", "/api/tasks", "/api/notifications",
    "/api/reports/summary", "/api/reports/leads_by_source",
    "/api/locations/provinces", "/api/locations/cities", "/api/locations/suburbs",
])
def test_regression_endpoints_authed(headers, path):
    r = requests.get(f"{BASE_URL}{path}", headers=headers, timeout=30)
    assert r.status_code == 200, f"{path} → {r.status_code}: {r.text[:200]}"


def test_public_captcha():
    r = requests.get(f"{BASE_URL}/api/public/challenge", timeout=15)
    assert r.status_code == 200
    j = r.json()
    assert "token" in j and "question" in j


def _get_captcha():
    """Fetch a challenge and return (token, answer). Question format:
    'Type these letters/numbers: XXXXX'"""
    cap = requests.get(f"{BASE_URL}/api/public/challenge", timeout=15).json()
    q = cap["question"]
    if ":" in q:
        answer = q.split(":", 1)[1].strip()
    else:
        # arithmetic fallback
        expr = q.replace("?", "").replace("=", "").strip()
        a, op, b = expr.split()
        answer = str(eval(f"{a}{op}{b}"))
    return cap["token"], answer


def _create_public_lead(email: str, name: str = "TESTLead_ITER26") -> None:
    token, answer = _get_captcha()
    r = requests.post(f"{BASE_URL}/api/public/leads", timeout=30, json={
        "source": "contact_form", "name": name, "email": email,
        "phone": "+675 333 444", "message": "iter26 test",
        "verification_token": token, "verification_answer": answer,
    })
    assert r.status_code == 200, r.text


def test_property_scheme_enforcement(headers):
    # House without lot fields → 400
    r = requests.post(f"{BASE_URL}/api/properties", headers=headers, timeout=30, json={
        "title": "TEST_iter26_house", "property_type": "House", "listing_type": "sale",
        "location": "Port Moresby", "price": 100000, "total_area_ha": 0.1,
    })
    assert r.status_code == 400, r.text

    # Portion without portion number → 400
    r = requests.post(f"{BASE_URL}/api/properties", headers=headers, timeout=30, json={
        "title": "TEST_iter26_portion", "property_type": "Large Land – Portion / Customary",
        "location": "Port Moresby", "listing_type": "sale", "price": 100000, "total_area_ha": 1.0,
    })
    assert r.status_code == 400, r.text

    # Sale without total_area_ha → 400
    r = requests.post(f"{BASE_URL}/api/properties", headers=headers, timeout=30, json={
        "title": "TEST_iter26_noarea", "property_type": "House", "listing_type": "sale",
        "location": "Port Moresby", "price": 100000,
        "allotment_number": "1", "section_number": "1", "street_name": "X",
    })
    assert r.status_code == 400, r.text


# ----- Customer Communications -----
@pytest.fixture(scope="module")
def customer_id(headers):
    r = requests.post(f"{BASE_URL}/api/customers", headers=headers, timeout=30, json={
        "name": "TESTCust_ITER26_comm", "email": "iter26@testcust.example",
        "phone": "+675 111 222", "customer_type": "buyer", "source": "manual",
    })
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    yield cid
    requests.delete(f"{BASE_URL}/api/customers/{cid}", headers=headers, timeout=30)


@pytest.fixture(scope="module")
def lead_id(headers):
    email = "iter26lead@test.example"
    _create_public_lead(email)
    all_leads = requests.get(f"{BASE_URL}/api/leads", headers=headers, timeout=30).json()
    lid = next(l["id"] for l in all_leads if l.get("email") == email)
    yield lid
    requests.delete(f"{BASE_URL}/api/leads/{lid}", headers=headers, timeout=30)


def test_customer_comms_empty(headers, customer_id):
    r = requests.get(f"{BASE_URL}/api/customers/{customer_id}/communications", headers=headers, timeout=30)
    assert r.status_code == 200
    assert r.json() == []


def test_customer_comm_create(headers, customer_id):
    payload = {"kind": "note", "direction": "outbound", "subject": "Hi", "body": "Called customer today"}
    r = requests.post(f"{BASE_URL}/api/customers/{customer_id}/communications",
                      headers=headers, json=payload, timeout=30)
    assert r.status_code == 200, r.text
    doc = r.json()
    assert doc["parent_type"] == "customer"
    assert doc["parent_id"] == customer_id
    assert doc["customer_id"] == customer_id
    assert doc.get("lead_id") is None
    assert doc["body"] == "Called customer today"
    assert doc["agent_name"]

    # GET returns it
    r = requests.get(f"{BASE_URL}/api/customers/{customer_id}/communications", headers=headers, timeout=30)
    assert r.status_code == 200
    lst = r.json()
    assert len(lst) == 1
    assert lst[0]["id"] == doc["id"]


def test_customer_comm_invalid_customer_404(headers):
    r = requests.post(f"{BASE_URL}/api/customers/does-not-exist-xyz/communications",
                      headers=headers, timeout=30,
                      json={"kind": "note", "direction": "outbound", "body": "x"})
    assert r.status_code == 404


def test_customer_comm_empty_body_400(headers, customer_id):
    r = requests.post(f"{BASE_URL}/api/customers/{customer_id}/communications",
                      headers=headers, timeout=30,
                      json={"kind": "note", "direction": "outbound", "body": "   "})
    assert r.status_code == 400


def test_delete_customer_comm(headers, customer_id):
    r = requests.post(f"{BASE_URL}/api/customers/{customer_id}/communications", headers=headers,
                      json={"kind": "note", "direction": "outbound", "body": "to be deleted"}, timeout=30)
    cid = r.json()["id"]
    r = requests.delete(f"{BASE_URL}/api/communications/{cid}", headers=headers, timeout=30)
    assert r.status_code == 200
    lst = requests.get(f"{BASE_URL}/api/customers/{customer_id}/communications", headers=headers, timeout=30).json()
    assert not any(c["id"] == cid for c in lst)


def test_lead_comm_backward_compat(headers, lead_id):
    payload = {"kind": "call", "direction": "outbound", "subject": "Followup", "body": "spoke with lead"}
    r = requests.post(f"{BASE_URL}/api/leads/{lead_id}/communications", headers=headers, json=payload, timeout=30)
    assert r.status_code == 200, r.text
    doc = r.json()
    assert doc["parent_type"] == "lead"
    assert doc["lead_id"] == lead_id
    assert doc["parent_id"] == lead_id
    assert doc.get("customer_id") is None


def test_lead_comm_legacy_fallback(headers, lead_id):
    """Insert a legacy-shaped doc directly and confirm GET returns it."""
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        # Read from backend env
        be = dotenv_values("/app/backend/.env")
        mongo_url = mongo_url or be.get("MONGO_URL")
        db_name = db_name or be.get("DB_NAME")

    async def _do():
        cli = AsyncIOMotorClient(mongo_url)
        db = cli[db_name]
        legacy = {
            "id": "legacy-iter26-xyz", "lead_id": lead_id,
            "kind": "email", "direction": "inbound", "subject": "old",
            "body": "legacy doc", "agent_id": "sys", "agent_name": "sys",
            "created_at": "2020-01-01T00:00:00Z",
        }
        await db.communications.insert_one(legacy)
        cli.close()
        return legacy["id"]

    legacy_id = asyncio.get_event_loop().run_until_complete(_do())
    try:
        lst = requests.get(f"{BASE_URL}/api/leads/{lead_id}/communications", headers=headers, timeout=30).json()
        ids = [c["id"] for c in lst]
        assert legacy_id in ids, f"Legacy doc not returned; got {ids}"
    finally:
        requests.delete(f"{BASE_URL}/api/communications/{legacy_id}", headers=headers, timeout=30)


def test_customer_delete_cascade(headers):
    # Create fresh customer + 2 comms, delete customer, comms should be gone (via new endpoint list of same id → still 404-safe: GET returns [])
    r = requests.post(f"{BASE_URL}/api/customers", headers=headers, timeout=30, json={
        "name": "TESTCust_ITER26_cascade", "customer_type": "buyer", "source": "manual",
    })
    cid = r.json()["id"]
    for i in range(2):
        requests.post(f"{BASE_URL}/api/customers/{cid}/communications", headers=headers,
                      json={"kind": "note", "direction": "outbound", "body": f"n{i}"}, timeout=30)
    # Confirm 2 exist
    lst = requests.get(f"{BASE_URL}/api/customers/{cid}/communications", headers=headers, timeout=30).json()
    assert len(lst) == 2
    # Delete customer
    requests.delete(f"{BASE_URL}/api/customers/{cid}", headers=headers, timeout=30)
    # Comms should be cascade-deleted
    lst2 = requests.get(f"{BASE_URL}/api/customers/{cid}/communications", headers=headers, timeout=30).json()
    assert lst2 == []


def test_lead_delete_cascade(headers):
    email = "iter26cascade@test.example"
    _create_public_lead(email, "TESTLead_ITER26_cascade")
    all_leads = requests.get(f"{BASE_URL}/api/leads", headers=headers, timeout=30).json()
    lid = next(l["id"] for l in all_leads if l.get("email") == email)

    # 1 new-style + 1 legacy comm
    requests.post(f"{BASE_URL}/api/leads/{lid}/communications", headers=headers,
                  json={"kind": "note", "direction": "outbound", "body": "new"}, timeout=30)

    be = dotenv_values("/app/backend/.env")
    mongo_url = os.environ.get("MONGO_URL") or be.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME") or be.get("DB_NAME")

    async def _insert():
        cli = AsyncIOMotorClient(mongo_url)
        await cli[db_name].communications.insert_one({
            "id": "legacy-cascade-iter26", "lead_id": lid, "kind": "note",
            "direction": "inbound", "body": "legacy", "agent_id": "s", "agent_name": "s",
            "created_at": "2020-01-01T00:00:00Z",
        })
        cli.close()

    asyncio.get_event_loop().run_until_complete(_insert())

    lst_before = requests.get(f"{BASE_URL}/api/leads/{lid}/communications", headers=headers, timeout=30).json()
    assert len(lst_before) == 2

    requests.delete(f"{BASE_URL}/api/leads/{lid}", headers=headers, timeout=30)

    lst_after = requests.get(f"{BASE_URL}/api/leads/{lid}/communications", headers=headers, timeout=30).json()
    assert lst_after == []


def test_customer_vs_lead_isolation(headers, customer_id, lead_id):
    # Log against both, ensure they don't cross-appear
    requests.post(f"{BASE_URL}/api/customers/{customer_id}/communications", headers=headers,
                  json={"kind": "note", "direction": "outbound", "body": "CUST-ONLY-ISOLATION"}, timeout=30)
    requests.post(f"{BASE_URL}/api/leads/{lead_id}/communications", headers=headers,
                  json={"kind": "note", "direction": "outbound", "body": "LEAD-ONLY-ISOLATION"}, timeout=30)

    cust_list = requests.get(f"{BASE_URL}/api/customers/{customer_id}/communications", headers=headers, timeout=30).json()
    lead_list = requests.get(f"{BASE_URL}/api/leads/{lead_id}/communications", headers=headers, timeout=30).json()

    cust_bodies = [c["body"] for c in cust_list]
    lead_bodies = [l["body"] for l in lead_list]
    assert "CUST-ONLY-ISOLATION" in cust_bodies
    assert "LEAD-ONLY-ISOLATION" not in cust_bodies
    assert "LEAD-ONLY-ISOLATION" in lead_bodies
    assert "CUST-ONLY-ISOLATION" not in lead_bodies
