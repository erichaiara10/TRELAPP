"""PNG Realty backend API tests."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://req-to-web-1.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@pngrealty.pg", "password": "Admin@123"}
SALES = {"email": "sales@pngrealty.pg", "password": "Password@123"}


@pytest.fixture(scope="function")
def s():
    # Fresh session per test to avoid access_token cookie pollution
    return requests.Session()


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def admin_token():
    return _login(ADMIN["email"], ADMIN["password"])


@pytest.fixture(scope="session")
def sales_token():
    return _login(SALES["email"], SALES["password"])


def H(tok):
    return {"Authorization": f"Bearer {tok}"}


# ---- Health ----
def test_health(s):
    r = s.get(f"{API}/")
    assert r.status_code == 200
    assert r.json().get("ok") is True


# ---- Auth ----
def test_login_wrong_password(s):
    r = s.post(f"{API}/auth/login", json={"email": ADMIN["email"], "password": "wrong"})
    assert r.status_code == 401


def test_auth_me(s, admin_token):
    r = s.get(f"{API}/auth/me", headers=H(admin_token))
    assert r.status_code == 200
    assert r.json()["email"] == ADMIN["email"]
    assert r.json()["role"] == "system_admin"


def test_auth_me_no_token(s):
    r = s.get(f"{API}/auth/me")
    assert r.status_code == 401


# ---- Properties (public) ----
def test_list_properties(s):
    r = s.get(f"{API}/properties")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list) and len(data) >= 1
    assert "_id" not in data[0]


def test_properties_featured_filter(s):
    r = s.get(f"{API}/properties", params={"featured": "true"})
    assert r.status_code == 200
    for p in r.json():
        assert p.get("featured") is True


def test_properties_listing_type_filter(s):
    r = s.get(f"{API}/properties", params={"listing_type": "sale"})
    assert r.status_code == 200
    for p in r.json():
        assert p["listing_type"] == "sale"


def test_property_detail_and_404(s):
    all_props = s.get(f"{API}/properties").json()
    pid = all_props[0]["id"]
    r = s.get(f"{API}/properties/{pid}")
    assert r.status_code == 200
    assert r.json()["id"] == pid
    r2 = s.get(f"{API}/properties/does-not-exist-xyz")
    assert r2.status_code == 404


# ---- Public lead intake ----
def test_public_lead_sell_form(s, admin_token):
    payload = {"source": "sell_form", "name": "TEST_Seller", "email": "TEST_sell@example.com",
               "phone": "+675 000 0001", "message": "sell my house"}
    r = s.post(f"{API}/public/leads", json=payload)
    assert r.status_code == 200
    assert r.json().get("ok") is True
    lid = r.json()["lead_id"]
    leads = requests.get(f"{API}/leads", headers=H(admin_token)).json()
    match = [l for l in leads if l["id"] == lid]
    assert match and match[0]["source"] == "sell_form"
    assert match[0].get("customer_id")  # customer created


def test_public_lead_wanted_creates_requirement(s, admin_token):
    payload = {"source": "wanted_form", "name": "TEST_Wanted", "email": "TEST_want@example.com",
               "phone": "+675 000 0002", "message": "want a house",
               "payload": {"intent": "buy", "property_type": "house",
                           "min_price": 100000, "max_price": 800000,
                           "min_bedrooms": 3, "locations": ["Port Moresby"]}}
    r = s.post(f"{API}/public/leads", json=payload)
    assert r.status_code == 200
    lid = r.json()["lead_id"]
    leads = s.get(f"{API}/leads", headers=H(admin_token)).json()
    lead = next(l for l in leads if l["id"] == lid)
    assert lead.get("requirement_id")
    assert lead.get("customer_id")


def test_public_inspection(s, admin_token):
    prop = s.get(f"{API}/properties").json()[0]
    payload = {"property_id": prop["id"], "customer_name": "TEST_Inspector",
               "customer_email": "TEST_insp@example.com", "customer_phone": "+675 000 0003",
               "preferred_date": "2026-02-01"}
    r = s.post(f"{API}/public/inspections", json=payload)
    assert r.status_code == 200
    iid = r.json()["inspection_id"]
    inspections = s.get(f"{API}/inspections", headers=H(admin_token)).json()
    assert any(i["id"] == iid for i in inspections)


def test_public_inspection_bad_property(s):
    r = s.post(f"{API}/public/inspections",
               json={"property_id": "nope", "customer_name": "TEST_x"})
    assert r.status_code == 404


# ---- Public requirements ----
def test_public_requirements_no_pii(s):
    r = s.get(f"{API}/requirements/public")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list) and len(data) >= 1
    for req in data:
        assert "customer_name" not in req
        assert "customer_id" not in req


# ---- Staff CRUD ----
def test_list_leads_customers_inspections(s, admin_token):
    for path in ("leads", "customers", "inspections", "requirements"):
        r = s.get(f"{API}/{path}", headers=H(admin_token))
        assert r.status_code == 200, f"{path}: {r.text}"
        assert isinstance(r.json(), list)


def test_lead_status_persist(s, admin_token):
    leads = s.get(f"{API}/leads", headers=H(admin_token)).json()
    assert leads
    lid = leads[0]["id"]
    r = s.put(f"{API}/leads/{lid}", json={"status": "qualified"}, headers=H(admin_token))
    assert r.status_code == 200
    # re-fetch
    got = next(l for l in s.get(f"{API}/leads", headers=H(admin_token)).json() if l["id"] == lid)
    assert got["status"] == "qualified"


def test_tasks_crud(s, admin_token):
    r = s.post(f"{API}/tasks", json={"title": "TEST_task", "priority": "high"}, headers=H(admin_token))
    assert r.status_code == 200
    tid = r.json()["id"]
    r2 = s.put(f"{API}/tasks/{tid}", json={"status": "done"}, headers=H(admin_token))
    assert r2.status_code == 200
    got = next(t for t in s.get(f"{API}/tasks", headers=H(admin_token)).json() if t["id"] == tid)
    assert got["status"] == "done"
    r3 = s.delete(f"{API}/tasks/{tid}", headers=H(admin_token))
    assert r3.status_code == 200


def test_matching(s, admin_token):
    reqs = s.get(f"{API}/requirements", headers=H(admin_token)).json()
    assert reqs
    rid = reqs[0]["id"]
    r = s.get(f"{API}/matching/{rid}", headers=H(admin_token))
    assert r.status_code == 200
    body = r.json()
    matches = body.get("matches") if isinstance(body, dict) else body
    assert isinstance(matches, list)
    scores = [m.get("score", 0) for m in matches]
    assert scores == sorted(scores, reverse=True)


# ---- Property CRUD (authed) ----
def test_property_crud(s, admin_token):
    payload = {"title": "TEST_Prop", "listing_type": "sale", "property_type": "house",
               "price": 500000, "location": "Port Moresby", "bedrooms": 3, "bathrooms": 2}
    r = s.post(f"{API}/properties", json=payload, headers=H(admin_token))
    assert r.status_code == 200
    pid = r.json()["id"]
    r2 = s.put(f"{API}/properties/{pid}", json={"price": 550000, "title": "TEST_Prop"},
               headers=H(admin_token))
    assert r2.status_code == 200
    got = s.get(f"{API}/properties/{pid}").json()
    assert got["price"] == 550000
    r3 = s.delete(f"{API}/properties/{pid}", headers=H(admin_token))
    assert r3.status_code == 200
    assert s.get(f"{API}/properties/{pid}").status_code == 404


# ---- Users ----
def test_users_list(s, admin_token):
    r = s.get(f"{API}/users", headers=H(admin_token))
    assert r.status_code == 200
    assert any(u["email"] == ADMIN["email"] for u in r.json())


def test_users_create_admin_only(s, admin_token, sales_token):
    # non-admin forbidden
    r_forbidden = s.post(f"{API}/users",
        json={"email": "TEST_new@example.com", "password": "Pass@1234",
              "name": "TEST_new", "role": "sales_agent"}, headers=H(sales_token))
    assert r_forbidden.status_code == 403
    # admin allowed
    r_ok = s.post(f"{API}/users",
        json={"email": "TEST_created@example.com", "password": "Pass@1234",
              "name": "TEST_created", "role": "sales_agent"}, headers=H(admin_token))
    assert r_ok.status_code == 200
    uid = r_ok.json()["id"]
    s.delete(f"{API}/users/{uid}", headers=H(admin_token))


# ---- Content ----
def test_content_site_get_and_update(s, admin_token):
    r = s.get(f"{API}/content/site")
    assert r.status_code == 200
    original = r.json()
    orig_value = original.get("value", original) if isinstance(original, dict) else {}
    new_name = "PNG Realty Test"
    r2 = s.put(f"{API}/content/site", json={"site_name": new_name}, headers=H(admin_token))
    assert r2.status_code == 200
    got = s.get(f"{API}/content/site").json()
    site_name = got.get("value", got).get("site_name") if isinstance(got, dict) else None
    assert site_name == new_name
    # restore
    if orig_value.get("site_name"):
        s.put(f"{API}/content/site", json={"site_name": orig_value["site_name"]}, headers=H(admin_token))


# ---- Reports ----
def test_reports_summary(s, admin_token):
    r = s.get(f"{API}/reports/summary", headers=H(admin_token))
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)


def test_reports_leads_by_source(s, admin_token):
    r = s.get(f"{API}/reports/leads_by_source", headers=H(admin_token))
    assert r.status_code == 200
    assert isinstance(r.json(), list)
