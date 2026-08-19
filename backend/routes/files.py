"""Object-storage backed uploads with private property-advertising access."""
import hashlib
import logging
import os
from typing import Optional

import requests
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile

from core.db import db, new_id, now_iso
from core.security import get_current_user

router = APIRouter()
logger = logging.getLogger("trel")

STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
APP_NAME = "trel"

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_DOCUMENT_TYPES = ALLOWED_IMAGE_TYPES | {"application/pdf"}
EXT_FROM_MIME = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "application/pdf": "pdf",
}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_PROPERTY_PHOTOS = 20
MAX_PROPERTY_DOCUMENTS = 10
STAFF_ROLES = {
    "system_admin", "managing_director", "sales_agent",
    "leasing_agent", "marketing_officer",
}

_storage_key = None


def init_storage():
    global _storage_key
    if _storage_key or not EMERGENT_KEY:
        return _storage_key
    try:
        response = requests.post(
            f"{STORAGE_URL}/init",
            json={"emergent_key": EMERGENT_KEY},
            timeout=30,
        )
        response.raise_for_status()
        _storage_key = response.json()["storage_key"]
        logger.info("Storage initialised")
    except Exception as exc:
        logger.warning("Storage init failed: %s", exc)
    return _storage_key


def _put_object(path: str, data: bytes, content_type: str) -> dict:
    global _storage_key
    key = init_storage()
    if not key:
        raise HTTPException(503, "Storage unavailable")
    response = requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data,
        timeout=120,
    )
    if response.status_code == 403:
        _storage_key = None
        key = init_storage()
        response = requests.put(
            f"{STORAGE_URL}/objects/{path}",
            headers={"X-Storage-Key": key, "Content-Type": content_type},
            data=data,
            timeout=120,
        )
    response.raise_for_status()
    return response.json()


def _get_object(path: str):
    global _storage_key
    key = init_storage()
    if not key:
        raise HTTPException(503, "Storage unavailable")
    response = requests.get(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key},
        timeout=60,
    )
    if response.status_code == 403:
        _storage_key = None
        key = init_storage()
        response = requests.get(
            f"{STORAGE_URL}/objects/{path}",
            headers={"X-Storage-Key": key},
            timeout=60,
        )
    if response.status_code == 404:
        raise HTTPException(404, "Stored file not found")
    response.raise_for_status()
    return response.content, response.headers.get(
        "Content-Type", "application/octet-stream"
    )


def _valid_signature(content_type: str, data: bytes) -> bool:
    if content_type == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff") and data.rstrip().endswith(b"\xff\xd9")
    if content_type == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/webp":
        return len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP"
    if content_type == "application/pdf":
        return data.startswith(b"%PDF-") and b"%%EOF" in data[-2048:]
    return False


def _require_advertiser(user: dict):
    if user.get("role") not in {"property_advertiser", "advertiser"}:
        raise HTTPException(403, "A Property Advertiser account is required")


def _safe_filename(filename: Optional[str]) -> str:
    value = (filename or "upload").replace("\\", "/").split("/")[-1].strip()
    return value[:200] or "upload"


async def _read_validated_file(file: UploadFile, category: str):
    content_type = (file.content_type or "").lower()
    allowed = ALLOWED_IMAGE_TYPES if category == "photo" else ALLOWED_DOCUMENT_TYPES
    if content_type not in allowed:
        expected = "JPG, PNG or WebP" if category == "photo" else "JPG, PNG, WebP or PDF"
        raise HTTPException(400, f"Only {expected} files are allowed")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(400, "File exceeds 10 MB limit")
    if len(data) < 12 or not _valid_signature(content_type, data):
        raise HTTPException(400, "File is empty, corrupted or does not match its declared type")
    return data, content_type


@router.post("/public/upload")
async def public_upload(file: UploadFile = File(...)):
    """Legacy public image upload used by the Sell/Wanted forms."""
    data, content_type = await _read_validated_file(file, "photo")
    ext = EXT_FROM_MIME[content_type]
    file_id = new_id()
    path = f"{APP_NAME}/uploads/public/{file_id}.{ext}"
    result = _put_object(path, data, content_type)
    await db.files.insert_one({
        "id": file_id,
        "storage_path": result["path"],
        "original_filename": _safe_filename(file.filename),
        "content_type": content_type,
        "size": result.get("size", len(data)),
        "is_deleted": False,
        "source": "public_upload",
        "visibility": "public",
        "created_at": now_iso(),
    })
    return {"id": file_id, "url": f"/api/files/{file_id}"}


@router.get("/files/{file_id}")
async def download_public_file(file_id: str):
    """Public download is limited to legacy public uploads and approved photos."""
    record = await db.files.find_one(
        {"id": file_id, "is_deleted": False, "visibility": "public"},
        {"_id": 0},
    )
    if not record:
        raise HTTPException(404, "File not found")
    data, detected_type = _get_object(record["storage_path"])
    return Response(
        content=data,
        media_type=record.get("content_type") or detected_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.post("/property-advertising/advertiser/files")
async def upload_property_advertising_file(
    category: str = Form(...),
    document_type: Optional[str] = Form(default=None),
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    """Upload an owner-scoped A06 photo or private supporting document."""
    _require_advertiser(user)
    if category not in {"photo", "document"}:
        raise HTTPException(400, "category must be photo or document")
    if document_type and len(document_type) > 120:
        raise HTTPException(400, "Document type is too long")

    existing_count = await db.files.count_documents({
        "owner_user_id": user["id"],
        "scope": "property_advertising",
        "category": category,
        "is_deleted": False,
        "submission_reference": None,
    })
    limit = MAX_PROPERTY_PHOTOS if category == "photo" else MAX_PROPERTY_DOCUMENTS
    if existing_count >= limit:
        raise HTTPException(400, f"Maximum {limit} {category} files per draft")

    data, content_type = await _read_validated_file(file, category)
    digest = hashlib.sha256(data).hexdigest()
    duplicate = await db.files.find_one({
        "owner_user_id": user["id"],
        "scope": "property_advertising",
        "category": category,
        "sha256": digest,
        "is_deleted": False,
        "submission_reference": None,
    }, {"_id": 0})
    if duplicate:
        raise HTTPException(409, "This file has already been uploaded to the current draft")

    current_draft = await db.pa_drafts.find_one(
        {"owner_user_id": user["id"], "status": {"$ne": "submitted"}},
        {"_id": 0},
        sort=[("updated_at", -1)],
    )
    file_id = new_id()
    ext = EXT_FROM_MIME[content_type]
    path = (
        f"{APP_NAME}/uploads/property-advertising/"
        f"{user['id']}/{file_id}.{ext}"
    )
    result = _put_object(path, data, content_type)
    timestamp = now_iso()
    record = {
        "id": file_id,
        "storage_path": result["path"],
        "original_filename": _safe_filename(file.filename),
        "content_type": content_type,
        "size": result.get("size", len(data)),
        "sha256": digest,
        "scope": "property_advertising",
        "category": category,
        "document_type": (document_type or "").strip() or None,
        "owner_user_id": user["id"],
        "draft_id": current_draft.get("id") if current_draft else None,
        "submission_reference": None,
        "visibility": "private",
        "is_deleted": False,
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    await db.files.insert_one(record)
    if category == "document" and record.get("document_type") == "identity":
        advertiser = await db.pa_advertisers.find_one(
            {"owner_user_id": user["id"]}, {"_id": 0},
        )
        if advertiser:
            identity_entry = {
                "id": new_id(),
                "file_id": file_id,
                "url": f"/api/property-advertising/files/{file_id}",
                "kind": "government_id",
                "filename": record["original_filename"],
                "uploaded_at": timestamp,
            }
            await db.pa_advertisers.update_one(
                {"reference": advertiser["reference"], "owner_user_id": user["id"]},
                {
                    "$push": {"identity_documents": identity_entry},
                    "$set": {
                        "identity_status": "Pending review",
                        "updated_at": timestamp,
                    },
                },
            )
    if current_draft:
        await db.pa_drafts.update_one(
            {"id": current_draft["id"], "owner_user_id": user["id"]},
            {
                "$addToSet": {"file_ids": file_id},
                "$set": {"updated_at": timestamp},
            },
        )
    public_record = {
        key: value for key, value in record.items()
        if key not in {"_id", "storage_path", "sha256", "owner_user_id"}
    }
    public_record["url"] = f"/api/property-advertising/files/{file_id}"
    return public_record


@router.get("/property-advertising/advertiser/files")
async def list_property_advertising_files(
    submission_reference: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    _require_advertiser(user)
    query = {
        "owner_user_id": user["id"],
        "scope": "property_advertising",
        "is_deleted": False,
    }
    if submission_reference:
        query["submission_reference"] = submission_reference
    records = await db.files.find(
        query,
        {"_id": 0, "storage_path": 0, "sha256": 0, "owner_user_id": 0},
    ).sort("created_at", 1).to_list(200)
    for record in records:
        record["url"] = f"/api/property-advertising/files/{record['id']}"
    return records


@router.delete("/property-advertising/advertiser/files/{file_id}")
async def delete_property_advertising_file(
    file_id: str,
    user: dict = Depends(get_current_user),
):
    _require_advertiser(user)
    record = await db.files.find_one({
        "id": file_id,
        "owner_user_id": user["id"],
        "scope": "property_advertising",
        "is_deleted": False,
    }, {"_id": 0})
    if not record:
        raise HTTPException(404, "File not found")
    if record.get("submission_reference"):
        raise HTTPException(400, "Submitted files cannot be removed; return the listing for correction")
    timestamp = now_iso()
    await db.files.update_one(
        {"id": file_id, "owner_user_id": user["id"]},
        {"$set": {"is_deleted": True, "updated_at": timestamp}},
    )
    if record.get("draft_id"):
        await db.pa_drafts.update_one(
            {"id": record["draft_id"], "owner_user_id": user["id"]},
            {"$pull": {"file_ids": file_id}, "$set": {"updated_at": timestamp}},
        )
    return {"ok": True, "id": file_id}


@router.get("/property-advertising/files/{file_id}")
async def download_property_advertising_file(
    file_id: str,
    user: dict = Depends(get_current_user),
):
    """Owner or authorised staff only. Private files never use public cache."""
    record = await db.files.find_one(
        {"id": file_id, "scope": "property_advertising", "is_deleted": False},
        {"_id": 0},
    )
    if not record:
        raise HTTPException(404, "File not found")
    is_owner = record.get("owner_user_id") == user["id"]
    is_staff = user.get("role") in STAFF_ROLES
    if not is_owner and not is_staff:
        raise HTTPException(403, "You are not authorised to access this file")
    data, detected_type = _get_object(record["storage_path"])
    disposition = "inline" if record.get("category") == "photo" else "attachment"
    filename = _safe_filename(record.get("original_filename"))
    return Response(
        content=data,
        media_type=record.get("content_type") or detected_type,
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": f'{disposition}; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )
