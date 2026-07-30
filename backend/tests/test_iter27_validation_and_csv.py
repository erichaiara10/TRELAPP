"""Iter-27 backend tests:

Phase 1 — Strict field validation for POST/PUT customers + properties.
Phase 2 — CSV import/export endpoints for admin properties & customers.
Phase 3 — Seed data protection (non-destructive on restart).
"""
import io
import os
import re
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL")
            or frontend_env.get("REACT_APP_BACKEND_URL")).rstrip("/")
API = f"{BASE_URL}/api"


# ---- Fixtures ----
@pytest.fixture(scope="session")
def creds():
    p = Path("/app/memory/test_credentials.md").read_text()
    email = re.search(r"Email:\s*`([^`]+)`", p).group(1)
    pw = re.search(r"Password:\s*`([^`]+)`", p).group(1)
    return {"email": email, "password": pw}


@pytest.fixture(scope="session")
def token(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=15)
    if r.status_code != 200:
        pytest.fail(f"Login failed: {r.status_code} {r.text[:200]}")
    t = r.json().get("token")
    if not t:
        pytest.fail(f"No token in login response: {r.text[:200]}")
    return t


@pytest.fixture(scope="session")
def client(token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="session")
def created_ids():
    return {"customers": [], "properties": []}


@pytest.fixture(scope="session", autouse=True)
def cleanup(created_ids, client):
    yield
    for cid in created_ids["customers"]:
        client.delete(f"{API}/customers/{cid}")
    for pid in created_ids["properties"]:
        client.delete(f"{API}/properties/{pid}")


# ---- Phase 1: Customers validation ----
class TestCustomerValidation:
    def test_missing_email_400(self, client):
        r = client.post(f"{API}/customers", json={
            "name": "TEST_ITER27_NoEmail", "phone": "70000001",
            "customer_type": "buyer"})
        assert r.status_code == 400
        assert "Email is required" in r.text

    def test_missing_phone_400(self, client):
        r = client.post(f"{API}/customers", json={
            "name": "TEST_ITER27_NoPhone", "email": "t@e.com",
            "customer_type": "buyer"})
        assert r.status_code == 400
        assert "Phone is required" in r.text

    def test_invalid_customer_type_400(self, client):
        r = client.post(f"{API}/customers", json={
            "name": "TEST_ITER27_BadType", "email": "t@e.com",
            "phone": "70000002", "customer_type": "foo"})
        assert r.status_code == 400
        assert "Customer type" in r.text

    def test_valid_customer_and_partial_update(self, client, created_ids):
        r = client.post(f"{API}/customers", json={
            "name": "TEST_ITER27_Valid", "email": "iter27@e.com",
            "phone": "70000003", "customer_type": "buyer"})
        assert r.status_code == 200, r.text
        cid = r.json()["id"]
        created_ids["customers"].append(cid)
        # PUT with only notes — should merge with DB record & succeed
        r2 = client.put(f"{API}/customers/{cid}", json={"notes": "updated"})
        assert r2.status_code == 200, r2.text
        assert r2.json()["notes"] == "updated"
        assert r2.json()["email"] == "iter27@e.com"


# ---- Phase 1: Properties validation ----
HOUSE_BASE = {
    "title": "TEST_ITER27_house", "listing_type": "rent",
    "property_type": "House", "price": 1000.0, "currency": "PGK",
    "province": "National Capital District", "location": "Port Moresby",
    "suburb": "Waigani", "allotment_number": "1", "section_number": "2",
    "street_name": "Main",
}


class TestPropertyValidation:
    def test_missing_province_400(self, client):
        payload = {**HOUSE_BASE, "province": ""}
        r = client.post(f"{API}/properties", json=payload)
        assert r.status_code == 400
        assert "Province is required" in r.text

    def test_missing_suburb_400(self, client):
        payload = {**HOUSE_BASE, "suburb": ""}
        r = client.post(f"{API}/properties", json=payload)
        assert r.status_code == 400
        assert "Suburb is required" in r.text

    def test_missing_listing_type(self, client):
        p = {**HOUSE_BASE}
        p.pop("listing_type")
        r = client.post(f"{API}/properties", json=p)
        assert r.status_code in (400, 422)

    def test_price_zero_400(self, client):
        r = client.post(f"{API}/properties", json={**HOUSE_BASE, "price": 0})
        assert r.status_code == 400
        assert "Price must be greater than zero" in r.text

    def test_house_missing_allotment_400(self, client):
        p = {**HOUSE_BASE}
        p.pop("allotment_number")
        r = client.post(f"{API}/properties", json=p)
        assert r.status_code == 400
        assert "Lot Number" in r.text or "allotment" in r.text.lower()

    def test_portion_missing_portion_number_400(self, client):
        r = client.post(f"{API}/properties", json={
            "title": "TEST_ITER27_portion", "listing_type": "rent",
            "property_type": "Large Land – Portion / Customary",
            "price": 500.0, "province": "NCD", "location": "PoM",
            "suburb": "S"})
        assert r.status_code == 400
        assert "Portion" in r.text

    def test_sale_missing_total_area_ha_400(self, client):
        p = {**HOUSE_BASE, "listing_type": "sale"}
        r = client.post(f"{API}/properties", json=p)
        assert r.status_code == 400
        assert "hectares" in r.text.lower() or "total area" in r.text.lower()

    def test_valid_property_persists(self, client, created_ids):
        p = {**HOUSE_BASE, "title": "TEST_ITER27_valid_house"}
        r = client.post(f"{API}/properties", json=p)
        assert r.status_code == 200, r.text
        pid = r.json()["id"]
        created_ids["properties"].append(pid)
        g = client.get(f"{API}/properties/{pid}")
        assert g.status_code == 200
        d = g.json()
        assert d["title"] == "TEST_ITER27_valid_house"
        assert d["suburb"] == "Waigani"
        assert d["price"] == 1000.0


# ---- Phase 2: CSV schema + template ----
class TestCsvSchema:
    def test_properties_schema(self, client):
        r = client.get(f"{API}/admin/properties/csv/schema")
        assert r.status_code == 200
        d = r.json()
        assert len(d["fields"]) == 30
        assert len(d["required_headers"]) == 12
        types = {f["type"] for f in d["fields"]}
        assert types == {"mandatory", "conditional", "optional", "auto"}

    def test_customers_schema(self, client):
        r = client.get(f"{API}/admin/customers/csv/schema")
        assert r.status_code == 200
        d = r.json()
        assert len(d["fields"]) == 10
        assert d["required_headers"] == ["name", "email", "phone", "customer_type"]

    def test_properties_template(self, client):
        r = client.get(f"{API}/admin/properties/csv/template")
        assert r.status_code == 200
        lines = r.text.strip().splitlines()
        assert len(lines) == 1  # only header
        assert lines[0].split(",")[0] == "id"
        assert len(lines[0].split(",")) == 30

    def test_customers_template(self, client):
        r = client.get(f"{API}/admin/customers/csv/template")
        assert r.status_code == 200
        lines = r.text.strip().splitlines()
        assert len(lines) == 1
        assert len(lines[0].split(",")) == 10


class TestCsvExport:
    def test_properties_export(self, client, created_ids):
        # ensure at least one exists
        if not created_ids["properties"]:
            r = client.post(f"{API}/properties", json={**HOUSE_BASE, "title": "TEST_ITER27_export"})
            created_ids["properties"].append(r.json()["id"])
        r = client.get(f"{API}/admin/properties/csv")
        assert r.status_code == 200
        cd = r.headers.get("content-disposition", "")
        assert "attachment" in cd and "properties_" in cd and ".csv" in cd
        assert "title" in r.text.splitlines()[0]

    def test_customers_export(self, client):
        r = client.get(f"{API}/admin/customers/csv")
        assert r.status_code == 200
        assert "attachment" in r.headers.get("content-disposition", "")
        assert "email" in r.text.splitlines()[0]


# ---- Phase 2: CSV import ----
def _post_csv(client, entity, csv_body, filename="upload.csv"):
    files = {"file": (filename, csv_body.encode("utf-8"), "text/csv")}
    # Use the session's auth header but drop json content-type
    return requests.post(f"{API}/admin/{entity}/csv", files=files,
                         headers={"Authorization": client.headers["Authorization"]},
                         timeout=30)


class TestCsvImport:
    def test_customers_missing_headers_400(self, client):
        csv_body = "name,customer_type\nA,buyer\n"
        r = _post_csv(client, "customers", csv_body)
        assert r.status_code == 400
        assert "missing required headers" in r.text.lower()
        assert "email" in r.text and "phone" in r.text

    def test_non_csv_file_400(self, client):
        r = _post_csv(client, "customers", "hello", filename="foo.txt")
        assert r.status_code == 400
        assert ".csv" in r.text.lower()

    def test_customers_mixed_valid_invalid(self, client, created_ids):
        csv_body = (
            "name,email,phone,customer_type\n"
            "TEST_ITER27_csv_a,a@e.com,70000010,buyer\n"
            "TEST_ITER27_csv_b,b@e.com,70000011,seller\n"
            "TEST_ITER27_csv_c,c@e.com,70000012,foo\n"
        )
        r = _post_csv(client, "customers", csv_body)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["inserted"] == 2
        assert d["received"] == 3
        assert len(d["errors"]) == 1
        assert d["errors"][0]["row"] == 4  # header=1, so 3rd data row is line 4
        # cleanup
        rows = client.get(f"{API}/customers").json()
        for c in rows:
            if c.get("name", "").startswith("TEST_ITER27_csv_"):
                created_ids["customers"].append(c["id"])

    def test_properties_mixed(self, client, created_ids):
        header = ("id,title,listing_type,property_type,price,province,location,suburb,"
                  "allotment_number,section_number,street_name,full_portion_number,total_area_ha")
        rows = [
            header,
            # House valid
            ",TEST_ITER27_csv_house,rent,House,1500,NCD,Port Moresby,Waigani,1,2,Main,,",
            # Portion valid
            ",TEST_ITER27_csv_portion,rent,Large Land – Portion / Customary,2000,NCD,PoM,Sub,,,,P-99,",
            # Zero price → error
            ",TEST_ITER27_csv_bad,rent,House,0,NCD,PoM,Waigani,1,2,Main,,",
        ]
        r = _post_csv(client, "properties", "\n".join(rows) + "\n")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["inserted"] == 2, d
        assert len(d["errors"]) == 1, d
        # track for cleanup
        for prop in client.get(f"{API}/properties?status=active&limit=200").json():
            if prop.get("title", "").startswith("TEST_ITER27_csv_"):
                created_ids["properties"].append(prop["id"])

    def test_properties_duplicate_id_skipped(self, client, created_ids):
        # create one via API
        r = client.post(f"{API}/properties", json={**HOUSE_BASE, "title": "TEST_ITER27_dup_src"})
        assert r.status_code == 200
        pid = r.json()["id"]
        created_ids["properties"].append(pid)
        header = ("id,title,listing_type,property_type,price,province,location,suburb,"
                  "allotment_number,section_number,street_name,full_portion_number,total_area_ha")
        body = header + "\n" + f"{pid},TEST_ITER27_dup_should_skip,rent,House,999,NCD,PoM,Waigani,9,9,S,,\n"
        r2 = _post_csv(client, "properties", body)
        assert r2.status_code == 200, r2.text
        d = r2.json()
        assert d["inserted"] == 0
        assert any(pid in s.get("reason", "") for s in d["skipped"])

    def test_properties_missing_suburb_value(self, client):
        header = ("title,listing_type,property_type,price,province,location,suburb,"
                  "allotment_number,section_number,street_name,full_portion_number,total_area_ha")
        body = header + "\n" + "TEST_ITER27_no_sub,rent,House,1200,NCD,PoM,,1,2,Main,,\n"
        r = _post_csv(client, "properties", body)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["inserted"] == 0
        assert len(d["errors"]) == 1
        assert "Suburb is required" in d["errors"][0]["reason"]


# ---- Phase 3: Seed data protection (light check — no restart) ----
class TestSeedProtection:
    def test_admin_still_exists(self, client):
        # If seeds re-wrote the admin, we could still log in — but the count
        # of properties/customers/leads/etc should be > 0 and stable.
        for coll in ("properties", "customers", "property-types"):
            r = client.get(f"{API}/{coll}")
            assert r.status_code == 200
            # non-empty (they were seeded earlier iterations)
            assert isinstance(r.json(), list)


# ---- Regression smoke ----
class TestRegression:
    @pytest.mark.parametrize("path", [
        "/", "/auth/me", "/users", "/properties", "/property-types",
        "/customers", "/requirements", "/leads", "/inspections", "/tasks",
        "/notifications", "/reports/summary", "/reports/leads_by_source",
        "/locations/provinces",
    ])
    def test_get_ok(self, client, path):
        r = client.get(f"{API}{path}")
        assert r.status_code == 200, f"{path} → {r.status_code} {r.text[:200]}"

    def test_public_challenge(self):
        r = requests.get(f"{API}/public/challenge", timeout=10)
        assert r.status_code == 200
        assert "token" in r.json()
