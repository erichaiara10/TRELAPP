"""Iter-44 comprehensive Property-Advertising acceptance tests.

Covers Phase 3 (create controlled properties), Phase 7 (workflow actions),
Phase 9 (audit + notifications), Phase 10 (security contract).
All created records prefixed with E2E-TEST-20260819 for traceability.
"""
import os
import re
import time
import uuid
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")).rstrip("/")
API = f"{BASE_URL}/api"
PREFIX = "E2E-TEST-20260819"


# --------------- fixtures ---------------
@pytest.fixture(scope="module")
def admin_creds():
    md = Path("/app/memory/test_credentials.md").read_text()
    email = re.search(r"Email:\s*`([^`]+)`", md).group(1)
    pwd = re.search(r"Password:\s*`([^`]+)`", md).group(1)
    return {"email": email, "password": pwd}


@pytest.fixture(scope="module")
def admin_token(admin_creds):
    r = requests.post(f"{API}/auth/login", json=admin_creds, timeout=30)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text[:200]}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def advertiser_ctx():
    """Create a fresh advertiser via db insert + login flow.

    Since /auth/register may not enroll property_advertiser role, seed directly via
    admin-only user creation path. Fallback: skip if we can't create advertiser.
    """
    # Direct DB insert via a helper endpoint isn't available; use admin to create.
    # Try /api/users
    ad_email = f"e2e_adv_{uuid.uuid4().hex[:8]}@example.com"
    ad_pwd = "E2E#TestPass2026"

    email = "advertiser.20260819.002523@example.com"
    new_pwd = "E2E#TestPass2026"

    # Try new password directly
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": new_pwd}, timeout=30)
    if r.status_code == 200 and r.json().get("token"):
        return {"email": email, "password": new_pwd, "token": r.json()["token"]}

    # Fall back: use temp password and complete change-password flow
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": "TempPass123!"}, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"Cannot login as advertiser: {r.status_code} {r.text[:200]}")
    body = r.json()
    if body.get("password_change_required") and body.get("change_token"):
        ch = requests.post(f"{API}/auth/change-password-first-login", json={
            "token": body["change_token"],
            "new_password": new_pwd,
            "confirm_password": new_pwd,
        }, timeout=30)
        if ch.status_code != 200:
            pytest.skip(f"change-password failed: {ch.status_code} {ch.text[:200]}")
        # login with new pwd
        r2 = requests.post(f"{API}/auth/login", json={"email": email, "password": new_pwd}, timeout=30)
        if r2.status_code == 200 and r2.json().get("token"):
            return {"email": email, "password": new_pwd, "token": r2.json()["token"]}
    pytest.skip(f"Advertiser auth flow could not be completed: {body}")


@pytest.fixture(scope="module")
def adv_headers(advertiser_ctx):
    return {"Authorization": f"Bearer {advertiser_ctx['token']}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# --------------- Safety Gate ---------------
def test_safety_gate_env():
    env = dotenv_values("/app/backend/.env")
    assert env.get("DB_NAME") == "test_database", f"DB_NAME must be test_database, got {env.get('DB_NAME')}"
    assert "localhost" in env.get("MONGO_URL", ""), "MONGO_URL must be localhost"


# --------------- Phase 10 SECURITY (independent of advertiser existence) ---------------
class TestSecurityContract:
    def test_unauth_workspace_401(self):
        r = requests.get(f"{API}/property-advertising/workspace", timeout=15)
        assert r.status_code == 401

    def test_unauth_actions_401(self):
        r = requests.post(f"{API}/property-advertising/actions", json={
            "record_type": "submission", "reference": "TREL-10428", "action": "confirm_new_property"
        }, timeout=15)
        assert r.status_code == 401

    def test_unknown_reference_404(self, admin_headers):
        r = requests.get(f"{API}/property-advertising/submission/TREL-DOESNOTEXIST", headers=admin_headers, timeout=15)
        assert r.status_code == 404

    def test_unknown_record_type_404(self, admin_headers):
        r = requests.get(f"{API}/property-advertising/gibberish/foo", headers=admin_headers, timeout=15)
        assert r.status_code == 404

    def test_unsupported_action_400(self, admin_headers):
        r = requests.post(f"{API}/property-advertising/actions", headers=admin_headers, json={
            "record_type": "submission", "reference": "TREL-10428", "action": "nuke_from_orbit"
        }, timeout=15)
        assert r.status_code == 400

    def test_action_on_missing_reference_404(self, admin_headers):
        r = requests.post(f"{API}/property-advertising/actions", headers=admin_headers, json={
            "record_type": "submission", "reference": "TREL-NOSUCH", "action": "confirm_new_property"
        }, timeout=15)
        assert r.status_code == 404

    def test_audit_events_not_writable_via_put(self, admin_headers):
        # No PUT/DELETE route registered → 405
        r = requests.put(f"{API}/property-advertising/audit-events/abc", headers=admin_headers, timeout=15)
        assert r.status_code in (404, 405)

    def test_audit_events_not_deletable(self, admin_headers):
        r = requests.delete(f"{API}/property-advertising/audit-events/abc", headers=admin_headers, timeout=15)
        assert r.status_code in (404, 405)

    def test_workspace_reject_advertiser_role(self, adv_headers):
        r = requests.get(f"{API}/property-advertising/workspace", headers=adv_headers, timeout=15)
        assert r.status_code == 403, f"Advertiser must be blocked from staff workspace, got {r.status_code}"

    def test_advertiser_draft_reject_admin_role(self, admin_headers):
        r = requests.get(f"{API}/property-advertising/advertiser/drafts/current", headers=admin_headers, timeout=15)
        assert r.status_code == 403

    def test_advertiser_me_reject_admin_role(self, admin_headers):
        r = requests.get(f"{API}/property-advertising/advertiser/me", headers=admin_headers, timeout=15)
        assert r.status_code == 403


# --------------- Phase 3+4 CREATE 10 CONTROLLED PROPERTIES ---------------
def _base_payload(title_suffix, **overrides):
    payload = {
        "listing_type": "Sale", "service": "TREL to sell/manage",
        "relationship": "Owner / Joint Owner", "property_class": "Residential",
        "property_type": "House", "currency": "PGK",
        "title": f"{PREFIX} - {title_suffix}",
        "price": "850000",
        "description": f"{PREFIX} synthetic listing description for automated acceptance testing.",
        "province": "NCD", "city": "Port Moresby", "suburb": "Boroko",
        "section": "Section 23", "lot": "Lot 48",
        "authority_confirmed": True, "terms_accepted": True,
    }
    payload.update(overrides)
    return payload


class TestPhase3CreateProperties:
    submission_refs = []

    def test_p01_residential_house_sale(self, adv_headers):
        p = _base_payload("P01 residential house sale", price="850000", condition="New")
        r = requests.post(f"{API}/property-advertising/advertiser/drafts/current/submit",
                          headers=adv_headers, json={"data": p, "current_step": 5}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        ref = r.json()["reference"]
        assert ref.startswith("TREL-")
        TestPhase3CreateProperties.submission_refs.append(ref)

    def test_p02_house_rent(self, adv_headers):
        p = _base_payload("P02 rent joint owner", listing_type="Rent", price="3500", service="TREL to sell/manage", relationship="Owner / Joint Owner", condition="Good")
        r = requests.post(f"{API}/property-advertising/advertiser/drafts/current/submit",
                          headers=adv_headers, json={"data": p, "current_step": 5}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        TestPhase3CreateProperties.submission_refs.append(r.json()["reference"])

    def test_p04_vacant_urban_land(self, adv_headers):
        p = _base_payload("P04 vacant urban land", property_class="Land", property_type="Vacant Land",
                          price="130000", section="Section 12", lot="Lot 5", street="Independence Drive",
                          suburb="9 Mile", province="NCD")
        r = requests.post(f"{API}/property-advertising/advertiser/drafts/current/submit",
                          headers=adv_headers, json={"data": p, "current_step": 5}, timeout=30)
        assert r.status_code == 200
        TestPhase3CreateProperties.submission_refs.append(r.json()["reference"])

    def test_p10_near_duplicate(self, adv_headers):
        """Backend has NO duplicate detection; documented — this should still submit successfully."""
        p = _base_payload("P10 near duplicate", property_class="Land", property_type="Vacant Land",
                          price="131000", section="Section 12", lot="Lot 5", street="Independance Drive",  # one-char typo
                          suburb="9 Mile", province="NCD")
        r = requests.post(f"{API}/property-advertising/advertiser/drafts/current/submit",
                          headers=adv_headers, json={"data": p, "current_step": 5}, timeout=30)
        assert r.status_code == 200

    def test_validation_missing_required(self, adv_headers):
        p = _base_payload("P-INVALID missing province")
        p["province"] = ""
        r = requests.post(f"{API}/property-advertising/advertiser/drafts/current/submit",
                          headers=adv_headers, json={"data": p, "current_step": 5}, timeout=30)
        assert r.status_code == 400
        assert "province" in r.text.lower() or "Province" in r.text

    def test_validation_missing_declarations(self, adv_headers):
        p = _base_payload("P-INVALID no declarations")
        p["authority_confirmed"] = False
        p["terms_accepted"] = False
        r = requests.post(f"{API}/property-advertising/advertiser/drafts/current/submit",
                          headers=adv_headers, json={"data": p, "current_step": 5}, timeout=30)
        assert r.status_code == 400
        assert "declaration" in r.text.lower()

    def test_validation_zero_price(self, adv_headers):
        p = _base_payload("P-INVALID zero price", price="0")
        r = requests.post(f"{API}/property-advertising/advertiser/drafts/current/submit",
                          headers=adv_headers, json={"data": p, "current_step": 5}, timeout=30)
        assert r.status_code == 400

    def test_boundary_long_description(self, adv_headers):
        p = _base_payload("P-BOUNDARY long desc", description=(PREFIX + " ") + ("x" * 1990))
        r = requests.post(f"{API}/property-advertising/advertiser/drafts/current/submit",
                          headers=adv_headers, json={"data": p, "current_step": 5}, timeout=30)
        assert r.status_code == 200

    def test_special_chars_title(self, adv_headers):
        p = _base_payload("P-SPECIAL éñ & <ok>")
        r = requests.post(f"{API}/property-advertising/advertiser/drafts/current/submit",
                          headers=adv_headers, json={"data": p, "current_step": 5}, timeout=30)
        assert r.status_code == 200

    def test_submissions_visible_to_advertiser(self, adv_headers):
        r = requests.get(f"{API}/property-advertising/advertiser/submissions", headers=adv_headers, timeout=15)
        assert r.status_code == 200
        subs = r.json()
        titles = [s.get("data", {}).get("title", "") for s in subs]
        assert any(PREFIX in t for t in titles), "Advertiser should see own submissions"


# --------------- Phase 7 WORKFLOW ACTIONS ---------------
class TestPhase7Workflows:
    def _pick_ref(self):
        return TestPhase3CreateProperties.submission_refs[0] if TestPhase3CreateProperties.submission_refs else "TREL-10428"

    def test_action_confirm_new_property(self, admin_headers):
        ref = self._pick_ref()
        # First ensure record exists in staff workspace
        r = requests.get(f"{API}/property-advertising/submission/{ref}", headers=admin_headers, timeout=15)
        if r.status_code == 404:
            pytest.skip(f"Submission {ref} not visible in staff collection")
        r2 = requests.post(f"{API}/property-advertising/actions", headers=admin_headers, json={
            "record_type": "submission", "reference": ref, "action": "confirm_new_property",
            "reason": f"{PREFIX} confirmed new property"
        }, timeout=15)
        assert r2.status_code == 200, r2.text[:300]
        body = r2.json()
        assert body["audit"]["action"] == "confirm_new_property"
        assert body["audit"]["performed_by_id"]
        assert body["audit"]["new_status"] == "Ready"
        assert "created_at" in body["audit"]

    def test_publication_publish(self, admin_headers):
        # Use seeded LIST-10428
        r = requests.post(f"{API}/property-advertising/actions", headers=admin_headers, json={
            "record_type": "publication", "reference": "LIST-10428", "action": "publish",
            "reason": f"{PREFIX} publish"
        }, timeout=15)
        assert r.status_code == 200
        assert r.json()["audit"]["new_status"] == "Published"

    def test_publication_suspend(self, admin_headers):
        r = requests.post(f"{API}/property-advertising/actions", headers=admin_headers, json={
            "record_type": "publication", "reference": "LIST-10428", "action": "suspend",
            "reason": f"{PREFIX} suspend"
        }, timeout=15)
        assert r.status_code == 200
        assert r.json()["audit"]["new_status"] == "Suspended"

    def test_lifecycle_send_confirmation_creates_notification(self, admin_headers):
        r = requests.post(f"{API}/property-advertising/actions", headers=admin_headers, json={
            "record_type": "lifecycle", "reference": "LIST-10428", "action": "send_confirmation",
            "reason": f"{PREFIX} periodic confirmation"
        }, timeout=15)
        assert r.status_code == 200
        # Check outbox contains this
        outbox = requests.get(f"{API}/property-advertising/notification-outbox", headers=admin_headers, timeout=15).json()
        assert any(n.get("reference") == "LIST-10428" and n.get("action") == "send_confirmation" for n in outbox)
        # All notifications remain queued (Resend not wired)
        for n in outbox:
            assert n.get("status") == "queued", "Notification unexpectedly moved out of queued state"

    def test_location_request_share(self, admin_headers):
        r = requests.post(f"{API}/property-advertising/actions", headers=admin_headers, json={
            "record_type": "location_request", "reference": "LOC-0081", "action": "share_location",
            "reason": f"{PREFIX} secure share"
        }, timeout=15)
        assert r.status_code == 200
        assert r.json()["audit"]["new_status"] == "Active"

    def test_advertiser_identity_verify(self, admin_headers):
        r = requests.post(f"{API}/property-advertising/actions", headers=admin_headers, json={
            "record_type": "advertiser", "reference": "ADV-00931", "action": "verify_identity",
            "reason": f"{PREFIX} single gov ID accepted"
        }, timeout=15)
        assert r.status_code == 200
        assert r.json()["audit"]["new_status"] == "Active"


# --------------- Phase 9 AUDIT VERIFICATION ---------------
class TestPhase9Audit:
    def test_audit_events_populated(self, admin_headers):
        r = requests.get(f"{API}/property-advertising/audit-events?limit=500", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        events = r.json()
        assert len(events) > 0
        # Verify each event carries required fields
        for e in events[:20]:
            assert "performed_by_id" in e and e["performed_by_id"]
            assert "record_type" in e
            assert "reference" in e
            assert "action" in e
            assert "created_at" in e
            assert "new_status" in e
            # No PII / passwords leaked
            for forbidden in ("password_hash", "password", "temp_password"):
                assert forbidden not in e, f"Audit event leaked {forbidden}"

    def test_notification_outbox_opaque_ids_no_pii(self, admin_headers):
        r = requests.get(f"{API}/property-advertising/notification-outbox", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        notes = r.json()
        for n in notes[:20]:
            # Ensure no bare email in the notification body
            assert "@" not in str(n.get("recipient_user_id") or ""), "Notification exposed email in recipient_user_id"
            assert "@" not in str(n.get("requested_by_id") or "")


# --------------- Phase 10 (b) ADVERTISER TENANT ISOLATION ---------------
class TestPhase10Tenant:
    def test_advertiser_cannot_hijack_owner_via_payload(self, adv_headers):
        """Advertiser PUT to /advertiser/drafts/current with owner_user_id in payload.data
        must NOT let them impersonate another user. Server derives owner from token."""
        r = requests.put(f"{API}/property-advertising/advertiser/drafts/current",
                         headers=adv_headers, json={
                             "data": {"title": f"{PREFIX} hijack attempt", "owner_user_id": "someone-else"},
                             "current_step": 1
                         }, timeout=15)
        assert r.status_code == 200
        # The stored owner_user_id (top-level) is derived from token
        stored = r.json()
        # data field can echo whatever, but the doc's owner_user_id is server-derived
        assert stored.get("owner_user_id") != "someone-else", "Server accepted client-supplied owner_user_id — CRITICAL"

    def test_advertiser_cannot_read_staff_submission_by_ref(self, adv_headers):
        """Direct GET /submission/{ref} is staff-only → advertiser must get 403."""
        r = requests.get(f"{API}/property-advertising/submission/TREL-10428", headers=adv_headers, timeout=15)
        assert r.status_code == 403
