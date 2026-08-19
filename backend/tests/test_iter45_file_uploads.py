"""D3 acceptance — file upload flows on A06 through S03A-T3/S02B/S03C.

Rebuilt after commit 5db6ca9 (the previous test file was on local-only
disk before the pull).  Runs against the live preview at
REACT_APP_BACKEND_URL and covers Phases A / B / D / E / F / G / H plus
the three new scenarios the user asked for in this iteration:

  * JPEG with permitted metadata AFTER the EOI marker is accepted.
  * PUT /advertiser/drafts/current rejects attachment ids owned by
    another account (draft-time binding check).
  * Cross-owner GET on /property-advertising/files/{id} returns 403.

Cache-Control assertion accepts a response containing 'no-store' as
passing (per user directive — do not require the 'private' directive
because the preview ingress rewrites it).
"""
import io
import os
import sys
import uuid

import bcrypt
import pytest
import requests
from PIL import Image
from pymongo import MongoClient

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_database")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

_url = os.environ.get("REACT_APP_BACKEND_URL")
if not _url:
    _url = "https://req-to-web-1.preview.emergentagent.com"
_url = _url.strip().split("\n")[0].split("\r")[0]
API = _url + "/api"
PREFIX = "E2E-TEST-20260819"

_mongo = MongoClient(os.environ["MONGO_URL"])
db = _mongo[os.environ["DB_NAME"]]


# ---------- Helpers ---------------------------------------------------------
def _make_jpeg(size=(24, 24), color=(30, 60, 90), extra_tail: bytes = b"") -> bytes:
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO(); img.save(buf, format="JPEG", quality=85)
    return buf.getvalue() + extra_tail


def _make_png(size=(24, 24)) -> bytes:
    img = Image.new("RGB", size, color=(200, 200, 40))
    buf = io.BytesIO(); img.save(buf, format="PNG"); return buf.getvalue()


def _make_webp(size=(24, 24)) -> bytes:
    img = Image.new("RGB", size, color=(20, 200, 200))
    buf = io.BytesIO(); img.save(buf, format="WEBP", quality=80); return buf.getvalue()


def _make_pdf() -> bytes:
    # Minimal but structurally-valid PDF.  Kept small (< 500 B).
    return (
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 100 100]>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n"
        b"0000000053 00000 n \n0000000094 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n141\n%%EOF\n"
    )


def _mk_advertiser(tag: str):
    email = f"e2e-adv-{tag}-{uuid.uuid4().hex[:6]}@example.com".lower()
    pw = f"E2Etest{uuid.uuid4().hex[:8]}Pass2026"
    user_id = uuid.uuid4().hex
    db.users.insert_one({
        "id": user_id, "email": email, "name": f"{PREFIX} {tag}",
        "role": "property_advertiser",
        "password_hash": bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode(),
        "must_change_password": False, "created_at": "2026-08-19T00:00:00+00:00",
    })
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=15)
    r.raise_for_status()
    return user_id, {"Authorization": f"Bearer {r.json()['token']}"}


def _cleanup_advertiser(user_id: str):
    db.users.delete_many({"id": user_id})
    db.pa_advertisers.delete_many({"owner_user_id": user_id})
    db.pa_drafts.delete_many({"owner_user_id": user_id})
    db.files.delete_many({"owner_user_id": user_id})
    submissions = list(db.pa_submissions.find({"owner_user_id": user_id}))
    refs = [s["reference"] for s in submissions]
    if refs:
        db.pa_submissions.delete_many({"reference": {"$in": refs}})
        db.pa_audit.delete_many({"reference": {"$in": refs}})
        db.pa_conflicts.delete_many({"reference": {"$in": refs}})
        db.pa_notifications.delete_many({"reference": {"$in": refs}})


# ---------- Fixtures --------------------------------------------------------
@pytest.fixture(scope="module")
def advertiser_a():
    uid, headers = _mk_advertiser("a")
    yield uid, headers
    _cleanup_advertiser(uid)


@pytest.fixture(scope="module")
def advertiser_b():
    uid, headers = _mk_advertiser("b")
    yield uid, headers
    _cleanup_advertiser(uid)


@pytest.fixture(scope="module")
def admin_headers():
    r = requests.post(f"{API}/auth/login",
                       json={"email": "admin@trel.com.pg", "password": "Admin@123"},
                       timeout=15)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _upload(headers, name, data, content_type, category="photo", extra=None):
    files = {"file": (name, data, content_type)}
    payload = {"category": category}
    if extra:
        payload.update(extra)
    return requests.post(f"{API}/property-advertising/advertiser/files",
                          headers=headers, files=files, data=payload, timeout=30)


# ---------- Phase A — Valid uploads (5 tests) ------------------------------
def test_a1_jpeg_upload_ok(advertiser_a):
    _, h = advertiser_a
    r = _upload(h, f"{PREFIX}-photo-a1.jpg", _make_jpeg(), "image/jpeg")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["category"] == "photo"
    assert body["original_filename"] == f"{PREFIX}-photo-a1.jpg"
    assert body["url"].endswith(f"/property-advertising/files/{body['id']}")


def test_a2_png_upload_ok(advertiser_a):
    _, h = advertiser_a
    r = _upload(h, f"{PREFIX}-photo-a2.png", _make_png(), "image/png")
    assert r.status_code == 200, r.text


def test_a3_webp_upload_ok(advertiser_a):
    _, h = advertiser_a
    r = _upload(h, f"{PREFIX}-photo-a3.webp", _make_webp(), "image/webp")
    assert r.status_code == 200, r.text


def test_a4_pdf_document_upload_ok(advertiser_a):
    _, h = advertiser_a
    r = _upload(h, f"{PREFIX}-doc-a4.pdf", _make_pdf(), "application/pdf",
                category="document", extra={"document_type": "title"})
    assert r.status_code == 200, r.text
    assert r.json()["category"] == "document"


def test_a5_multiple_photos_ok(advertiser_a):
    _, h = advertiser_a
    for i in range(3):
        r = _upload(h, f"{PREFIX}-photo-a5-{i}.jpg",
                     _make_jpeg(size=(16 + i, 16 + i)), "image/jpeg")
        assert r.status_code == 200


# ---------- Phase B — Rejections (5 tests) ---------------------------------
def test_b1_duplicate_rejected(advertiser_a):
    _, h = advertiser_a
    payload = _make_jpeg(size=(19, 19), color=(1, 2, 3))
    r1 = _upload(h, f"{PREFIX}-dup.jpg", payload, "image/jpeg")
    assert r1.status_code == 200
    r2 = _upload(h, f"{PREFIX}-dup-again.jpg", payload, "image/jpeg")
    assert r2.status_code in (400, 409), r2.text


def test_b2_oversized_rejected(advertiser_a):
    _, h = advertiser_a
    big = b"\xff\xd8\xff\xe0" + os.urandom(11 * 1024 * 1024)  # >10 MB
    r = _upload(h, f"{PREFIX}-big.jpg", big, "image/jpeg")
    assert r.status_code == 400, r.text
    assert "10" in r.text or "size" in r.text.lower() or "large" in r.text.lower()


def test_b3_unsupported_type_rejected(advertiser_a):
    _, h = advertiser_a
    r = _upload(h, f"{PREFIX}-bad.exe", b"MZ\x90\x00" + os.urandom(200),
                "application/x-msdownload")
    assert r.status_code in (400, 415), r.text


def test_b4_empty_file_rejected(advertiser_a):
    _, h = advertiser_a
    r = _upload(h, f"{PREFIX}-empty.jpg", b"", "image/jpeg")
    assert r.status_code == 400, r.text


def test_b5_corrupted_signature_rejected(advertiser_a):
    _, h = advertiser_a
    r = _upload(h, f"{PREFIX}-corrupt.jpg",
                b"not-a-real-jpeg-signature-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                "image/jpeg")
    assert r.status_code == 400, r.text


# ---------- Phase C (JPEG w/ trailing metadata) & Phase D (remove) --------
def test_c1_jpeg_with_metadata_after_eoi_accepted(advertiser_a):
    """New requirement: valid JPEG containing permitted metadata AFTER the
    EOI marker must be accepted."""
    _, h = advertiser_a
    tail = b"\x00\x00" + f"{PREFIX} EXIF-like metadata after EOI ".encode() * 4
    payload = _make_jpeg(size=(20, 20), extra_tail=tail)
    r = _upload(h, f"{PREFIX}-eoi-meta.jpg", payload, "image/jpeg")
    assert r.status_code == 200, r.text


def test_d1_remove_before_submit_ok(advertiser_a):
    _, h = advertiser_a
    r = _upload(h, f"{PREFIX}-tmp.jpg", _make_jpeg(size=(22, 22), color=(50, 50, 50)),
                "image/jpeg")
    fid = r.json()["id"]
    d = requests.delete(f"{API}/property-advertising/advertiser/files/{fid}",
                          headers=h, timeout=15)
    assert d.status_code == 200, d.text
    listing = requests.get(f"{API}/property-advertising/advertiser/files",
                            headers=h, timeout=15).json()
    assert not any(f["id"] == fid for f in listing)


# ---------- Phase D (cross-owner save-draft) --------------------------------
def test_d2_save_draft_rejects_cross_owner_attachment_id(advertiser_a, advertiser_b):
    """Draft-time binding check: PUT /drafts/current must reject a
    photo_file_id whose owner is a DIFFERENT advertiser."""
    _, h_a = advertiser_a
    _, h_b = advertiser_b
    r = _upload(h_a, f"{PREFIX}-hijack-src.jpg",
                 _make_jpeg(size=(25, 25), color=(11, 22, 33)), "image/jpeg")
    a_file_id = r.json()["id"]
    body = {
        "data": {"title": f"{PREFIX} - hijack attempt {uuid.uuid4().hex[:4]}",
                  "photo_file_ids": [a_file_id]},
        "current_step": 5,
    }
    r = requests.put(f"{API}/property-advertising/advertiser/drafts/current",
                      headers=h_b, json=body, timeout=15)
    assert r.status_code == 400, r.text
    assert "owned" in r.text.lower() or "missing" in r.text.lower()


# ---------- Phase E — Submit + immutability (2 tests) ----------------------
def test_e1_submit_binds_files_immutably(advertiser_a):
    _, h = advertiser_a
    # Fresh isolated photo + document just for this test.  Use random bytes
    # in each file to guarantee unique sha256 (avoid dedupe with earlier tests).
    photo_bytes = _make_jpeg(size=(30, 30), color=(70, 80, 90),
                              extra_tail=os.urandom(32))
    photo = _upload(h, f"{PREFIX}-submit-photo.jpg", photo_bytes,
                     "image/jpeg").json()["id"]
    pdf_bytes = _make_pdf() + b"%" + os.urandom(16).hex().encode() + b"\n"
    doc = _upload(h, f"{PREFIX}-submit-doc.pdf", pdf_bytes,
                    "application/pdf", category="document",
                    extra={"document_type": "title"}).json()["id"]
    payload = {"data": {
        "listing_type": "sale", "service": "advertise_only", "relationship": "owner",
        "property_class": "urban_residential", "property_type": "House",
        "title": f"{PREFIX} - submit test {uuid.uuid4().hex[:4]}",
        "price": "850000", "price_kind": "fixed",
        "description": f"{PREFIX} description body",
        "province": "NCD", "city": "Port Moresby", "suburb": "Boroko",
        "lot": f"E2E{uuid.uuid4().hex[:6]}", "section": f"S{uuid.uuid4().hex[:4]}",
        "authority_confirmed": True, "terms_accepted": True,
        "photo_file_ids": [photo], "document_file_ids": [doc],
    }, "current_step": 6}
    r = requests.post(f"{API}/property-advertising/advertiser/drafts/current/submit",
                       headers=h, json=payload, timeout=30)
    assert r.status_code == 200, r.text
    ref = r.json()["reference"]
    assert ref.startswith("TREL-")
    # Files must still be listed with submission_reference set.
    listing = requests.get(f"{API}/property-advertising/advertiser/files",
                            headers=h, timeout=15).json()
    photo_row = next((f for f in listing if f["id"] == photo), None)
    assert photo_row is not None
    assert photo_row.get("submission_reference") == ref


def test_e2_delete_submitted_file_rejected(advertiser_a):
    _, h = advertiser_a
    # Find a file already bound to a submission (from e1).
    listing = requests.get(f"{API}/property-advertising/advertiser/files",
                            headers=h, timeout=15).json()
    bound = next((f for f in listing if f.get("submission_reference")), None)
    assert bound is not None, "e1 must run first"
    d = requests.delete(f"{API}/property-advertising/advertiser/files/{bound['id']}",
                          headers=h, timeout=15)
    assert d.status_code in (400, 409), d.text


# ---------- Phase F — Staff visibility (2 tests) ---------------------------
def test_f1_admin_can_read_private_file(advertiser_a, admin_headers):
    _, h = advertiser_a
    listing = requests.get(f"{API}/property-advertising/advertiser/files",
                            headers=h, timeout=15).json()
    fid = listing[0]["id"]
    r = requests.get(f"{API}/property-advertising/files/{fid}",
                       headers=admin_headers, timeout=15)
    assert r.status_code == 200, r.text
    assert r.headers.get("Content-Type", "").startswith("image/")


def test_f2_staff_submission_detail_lists_files(admin_headers, advertiser_a):
    _, h_a = advertiser_a
    # Find TREL- from advertiser's own submissions.
    submissions = requests.get(f"{API}/property-advertising/advertiser/submissions",
                                headers=h_a, timeout=15).json()
    assert submissions, "advertiser must have at least one submission from e1"
    ref = submissions[0]["reference"]
    r = requests.get(f"{API}/property-advertising/submission/{ref}",
                       headers=admin_headers, timeout=15)
    assert r.status_code == 200, r.text


# ---------- Phase G — Access control (3 tests) -----------------------------
def test_g1_anonymous_gets_401(advertiser_a):
    _, h_a = advertiser_a
    listing = requests.get(f"{API}/property-advertising/advertiser/files",
                            headers=h_a, timeout=15).json()
    fid = listing[0]["id"]
    r = requests.get(f"{API}/property-advertising/files/{fid}", timeout=15)
    assert r.status_code == 401


def test_g2_second_advertiser_gets_403(advertiser_a, advertiser_b):
    """Previously skipped — now exercised with a real 2nd advertiser."""
    _, h_a = advertiser_a
    _, h_b = advertiser_b
    listing = requests.get(f"{API}/property-advertising/advertiser/files",
                            headers=h_a, timeout=15).json()
    fid = listing[0]["id"]
    r = requests.get(f"{API}/property-advertising/files/{fid}", headers=h_b, timeout=15)
    assert r.status_code == 403, r.text


def test_g3_cache_control_contains_no_store(advertiser_a):
    """Spec accepts a response containing 'no-store' as passing.  Do not
    assert 'private' — the preview ingress rewrites headers globally."""
    _, h_a = advertiser_a
    listing = requests.get(f"{API}/property-advertising/advertiser/files",
                            headers=h_a, timeout=15).json()
    fid = listing[0]["id"]
    r = requests.get(f"{API}/property-advertising/files/{fid}",
                       headers=h_a, timeout=15)
    assert r.status_code == 200
    cc = (r.headers.get("Cache-Control") or "").lower()
    assert "no-store" in cc, f"expected 'no-store', got {cc!r}"


# ---------- Phase H — Legacy public upload/download (2 tests) -------------
def test_h1_legacy_public_upload_and_download():
    """The pre-existing /api/public/upload → /api/files/{id} flow must
    keep working (regression)."""
    payload = _make_jpeg(size=(28, 28), color=(120, 30, 200))
    r = requests.post(f"{API}/public/upload",
                       files={"file": (f"{PREFIX}-public.jpg", payload, "image/jpeg")},
                       timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    fid = body.get("id") or body.get("file_id") or body.get("url", "").rsplit("/", 1)[-1]
    assert fid, body
    g = requests.get(f"{API}/files/{fid}", timeout=15)
    assert g.status_code == 200
    assert g.headers.get("Content-Type", "").startswith("image/")


def test_h2_private_file_not_reachable_through_public_path(advertiser_a):
    _, h_a = advertiser_a
    listing = requests.get(f"{API}/property-advertising/advertiser/files",
                            headers=h_a, timeout=15).json()
    fid = listing[0]["id"]
    r = requests.get(f"{API}/files/{fid}", timeout=15)
    assert r.status_code in (401, 403, 404), r.text
