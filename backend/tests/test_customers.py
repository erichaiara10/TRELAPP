"""Customer CRUD API tests"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://req-to-web-1.preview.emergentagent.com").rstrip("/")
ADMIN = {"email": "admin@trel.com.pg", "password": "Admin@123"}


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def test_list_customers_requires_auth():
    r = requests.get(f"{BASE_URL}/api/customers", timeout=30)
    assert r.status_code in (401, 403)


def test_post_requires_auth():
    r = requests.post(f"{BASE_URL}/api/customers", json={"name": "x"}, timeout=30)
    assert r.status_code in (401, 403)


def test_put_requires_auth():
    r = requests.put(f"{BASE_URL}/api/customers/xxx", json={"name": "x"}, timeout=30)
    assert r.status_code in (401, 403)


def test_delete_requires_auth():
    r = requests.delete(f"{BASE_URL}/api/customers/xxx", timeout=30)
    assert r.status_code in (401, 403)


def test_customer_full_crud(headers):
    # CREATE
    payload = {
        "name": "TESTCust_APIJohn",
        "email": "apijohn@testcust.example",
        "phone": "+675 100 200",
        "customer_type": "seller",
        "company": "TestCoAPI",
        "notes": "created by pytest",
        "source": "manual",
    }
    r = requests.post(f"{BASE_URL}/api/customers", json=payload, headers=headers, timeout=30)
    assert r.status_code == 200, r.text
    created = r.json()
    assert created["name"] == payload["name"]
    assert created["email"] == payload["email"]
    assert created["customer_type"] == "seller"
    cid = created["id"]

    # GET via LIST
    r = requests.get(f"{BASE_URL}/api/customers", headers=headers, timeout=30)
    assert r.status_code == 200
    found = [c for c in r.json() if c["id"] == cid]
    assert len(found) == 1
    assert found[0]["phone"] == payload["phone"]
    assert found[0]["company"] == "TestCoAPI"

    # UPDATE
    upd = {
        "name": "TESTCust_APIJohnUpdated",
        "email": "apijohn.updated@testcust.example",
        "phone": "+675 999",
        "customer_type": "landlord",
        "company": "TestCoAPI",
        "notes": "updated",
        "source": "manual",
    }
    r = requests.put(f"{BASE_URL}/api/customers/{cid}", json=upd, headers=headers, timeout=30)
    assert r.status_code == 200, r.text

    r = requests.get(f"{BASE_URL}/api/customers", headers=headers, timeout=30)
    row = next(c for c in r.json() if c["id"] == cid)
    assert row["name"] == "TESTCust_APIJohnUpdated"
    assert row["email"] == "apijohn.updated@testcust.example"
    assert row["phone"] == "+675 999"
    assert row["customer_type"] == "landlord"

    # DELETE
    r = requests.delete(f"{BASE_URL}/api/customers/{cid}", headers=headers, timeout=30)
    assert r.status_code == 200

    r = requests.get(f"{BASE_URL}/api/customers", headers=headers, timeout=30)
    assert not any(c["id"] == cid for c in r.json())


def test_cleanup_all_testcust(headers):
    r = requests.get(f"{BASE_URL}/api/customers", headers=headers, timeout=30)
    for c in r.json():
        if c.get("name", "").startswith("TESTCust_"):
            requests.delete(f"{BASE_URL}/api/customers/{c['id']}", headers=headers, timeout=30)
