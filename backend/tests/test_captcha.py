"""Alphanumeric CAPTCHA + public leads/inspections tests (iteration 7)."""
import os
import re
import pytest
import requests

def _read_frontend_env():
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip()
    raise RuntimeError("REACT_APP_BACKEND_URL not found")

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _read_frontend_env()).rstrip("/")
API = f"{BASE_URL}/api"


def get_challenge():
    r = requests.get(f"{API}/public/challenge")
    assert r.status_code == 200
    data = r.json()
    assert "question" in data and "token" in data
    return data


def test_challenge_shape():
    data = get_challenge()
    q = data["question"]
    # Format: "Type these letters/numbers: XXXXX"
    m = re.match(r"^Type these letters/numbers:\s*([A-Za-z0-9]{5})$", q)
    assert m, f"Unexpected question: {q}"
    code = m.group(1)
    # Ambiguous chars excluded (0/O/1/I/l)
    for ch in code:
        assert ch not in "0O1Il", f"Ambiguous char in code: {code}"


def test_challenge_uniqueness():
    """Different challenges typically produce different codes/tokens."""
    tokens = {get_challenge()["token"] for _ in range(3)}
    assert len(tokens) >= 2


def _extract_code(q):
    return re.search(r":\s*([A-Za-z0-9]{5})$", q).group(1)


def test_public_lead_correct_captcha_uppercase():
    ch = get_challenge()
    code = _extract_code(ch["question"])
    payload = {
        "source": "contact_form", "name": "TEST_UP", "email": "TEST_up@ex.com",
        "phone": "+675 000 1111", "message": "hi",
        "verification_answer": code, "verification_token": ch["token"],
    }
    r = requests.post(f"{API}/public/leads", json=payload)
    assert r.status_code == 200, r.text
    assert r.json().get("ok") is True


def test_public_lead_correct_captcha_lowercase():
    ch = get_challenge()
    code = _extract_code(ch["question"]).lower()
    payload = {
        "source": "contact_form", "name": "TEST_LO", "email": "TEST_lo@ex.com",
        "phone": "+675 000 1112", "message": "hi",
        "verification_answer": code, "verification_token": ch["token"],
    }
    r = requests.post(f"{API}/public/leads", json=payload)
    assert r.status_code == 200, r.text


def test_public_lead_wrong_captcha():
    ch = get_challenge()
    payload = {
        "source": "contact_form", "name": "TEST_BAD", "email": "TEST_bad@ex.com",
        "phone": "+675 000 1113", "message": "hi",
        "verification_answer": "ZZZZZ", "verification_token": ch["token"],
    }
    r = requests.post(f"{API}/public/leads", json=payload)
    assert r.status_code == 400
    assert "verification" in r.text.lower()


def test_public_lead_honeypot():
    ch = get_challenge()
    code = _extract_code(ch["question"])
    payload = {
        "source": "contact_form", "name": "TEST_HP", "email": "TEST_hp@ex.com",
        "phone": "+675 000 1114", "message": "hi",
        "verification_answer": code, "verification_token": ch["token"],
        "hp_website": "http://spam.example.com",
    }
    r = requests.post(f"{API}/public/leads", json=payload)
    assert r.status_code == 400


def test_public_inspection_with_captcha():
    props = requests.get(f"{API}/properties").json()
    assert props
    pid = props[0]["id"]
    ch = get_challenge()
    code = _extract_code(ch["question"])
    payload = {
        "property_id": pid,
        "customer_name": "TEST_Insp7", "customer_email": "TEST_insp7@ex.com",
        "customer_phone": "+675 000 1115", "preferred_date": "2026-03-01",
        "verification_answer": code, "verification_token": ch["token"],
    }
    r = requests.post(f"{API}/public/inspections", json=payload)
    assert r.status_code == 200, r.text
    assert r.json().get("ok") is True


def test_admin_login_regression():
    r = requests.post(f"{API}/auth/login",
                      json={"email": "admin@trel.com.pg", "password": "Admin@123"})
    assert r.status_code == 200
    j = r.json()
    assert j["role"] == "system_admin"
    tok = j["token"]
    # Admin properties list
    r2 = requests.get(f"{API}/properties", headers={"Authorization": f"Bearer {tok}"})
    assert r2.status_code == 200
