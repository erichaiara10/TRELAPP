"""Tests for the new PageContent multi-page API (/api/page/*)."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://req-to-web-1.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@trel.com.pg", "password": "Admin@123"}
SLUGS = ["home", "about", "sell", "buy", "rent", "wanted",
         "management", "corporate", "contact", "legal_privacy", "legal_terms"]


@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{API}/auth/login", json=ADMIN)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def H(tok):
    return {"Authorization": f"Bearer {tok}"}


# ---- GET /api/page/{slug} ----
@pytest.mark.parametrize("slug", SLUGS)
def test_get_page_all_slugs(slug):
    r = requests.get(f"{API}/page/{slug}")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["page"] == slug
    assert isinstance(data["sections"], dict)
    # merged defaults present -> non-empty for every slug
    assert len(data["sections"]) > 0, f"{slug} has empty sections (defaults missing)"


def test_get_page_nonexistent_returns_404():
    r = requests.get(f"{API}/page/nonexistent")
    assert r.status_code == 404


# ---- Auth guards ----
def test_put_page_without_auth_returns_401():
    r = requests.put(f"{API}/page/home", json={"sections": {}})
    assert r.status_code == 401


def test_post_list_without_auth_returns_401():
    r = requests.post(f"{API}/page/about/list/team", json={"name": "x"})
    assert r.status_code == 401


def test_delete_list_without_auth_returns_401():
    r = requests.delete(f"{API}/page/about/list/team/0")
    assert r.status_code == 401


# ---- PUT partial deep-merge ----
def test_put_about_partial_mission_preserves_defaults(admin_token):
    # Get baseline
    baseline = requests.get(f"{API}/page/about").json()["sections"]
    default_keys = set(baseline.keys())
    assert "mission" in default_keys, "about defaults missing mission"

    # Snapshot original mission so we can restore later
    original_mission = baseline.get("mission", {})

    # PUT only mission body
    r = requests.put(f"{API}/page/about",
                     json={"sections": {"mission": {"body": "Test mission"}}},
                     headers=H(admin_token))
    assert r.status_code == 200

    got = requests.get(f"{API}/page/about").json()["sections"]
    assert got["mission"]["body"] == "Test mission"
    # Other sections still present (deep merge with defaults)
    for k in default_keys:
        assert k in got, f"Section '{k}' lost after partial PUT"

    # Restore
    requests.put(f"{API}/page/about",
                 json={"sections": {"mission": original_mission}},
                 headers=H(admin_token))


# ---- Team list append + delete ----
def test_team_list_append_and_delete(admin_token):
    before = requests.get(f"{API}/page/about").json()["sections"].get("team", [])
    n_before = len(before) if isinstance(before, list) else 0

    marker = {"name": "TEST_Member_XYZ", "role": "QA", "photo": "", "bio": "Bio"}
    r = requests.post(f"{API}/page/about/list/team", json=marker, headers=H(admin_token))
    assert r.status_code == 200, r.text
    assert r.json()["count"] == n_before + 1

    after = requests.get(f"{API}/page/about").json()["sections"]["team"]
    assert len(after) == n_before + 1
    # Find the newly-appended member by unique name
    idx = next(i for i, m in enumerate(after) if m.get("name") == "TEST_Member_XYZ")

    # Delete it
    r2 = requests.delete(f"{API}/page/about/list/team/{idx}", headers=H(admin_token))
    assert r2.status_code == 200
    assert r2.json()["count"] == n_before

    final = requests.get(f"{API}/page/about").json()["sections"]["team"]
    assert all(m.get("name") != "TEST_Member_XYZ" for m in final)


def test_delete_out_of_range_returns_400(admin_token):
    r = requests.delete(f"{API}/page/about/list/team/9999", headers=H(admin_token))
    assert r.status_code == 400


def test_post_list_bad_section_returns_400(admin_token):
    # 'mission' is a dict, not a list
    r = requests.post(f"{API}/page/about/list/mission",
                      json={"foo": "bar"}, headers=H(admin_token))
    assert r.status_code == 400


# ---- Regression: legacy content endpoints still work ----
def test_regression_content_site():
    r = requests.get(f"{API}/content/site")
    assert r.status_code == 200


def test_regression_content_about():
    r = requests.get(f"{API}/content/about")
    assert r.status_code == 200
