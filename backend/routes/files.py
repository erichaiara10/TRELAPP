"""Object-storage backed public file upload + download."""
import logging
import os

import requests
from fastapi import APIRouter, File, HTTPException, Response, UploadFile

from core.db import db, new_id, now_iso

router = APIRouter()
logger = logging.getLogger("trel")

STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
APP_NAME = "trel"

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
EXT_FROM_MIME = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

_storage_key = None


def init_storage():
    global _storage_key
    if _storage_key or not EMERGENT_KEY:
        return _storage_key
    try:
        r = requests.post(f"{STORAGE_URL}/init",
                          json={"emergent_key": EMERGENT_KEY}, timeout=30)
        r.raise_for_status()
        _storage_key = r.json()["storage_key"]
        logger.info("Storage initialised")
    except Exception as e:
        logger.warning(f"Storage init failed: {e}")
    return _storage_key


def _put_object(path: str, data: bytes, content_type: str) -> dict:
    global _storage_key
    key = init_storage()
    if not key:
        raise HTTPException(503, "Storage unavailable")
    r = requests.put(f"{STORAGE_URL}/objects/{path}",
                     headers={"X-Storage-Key": key, "Content-Type": content_type},
                     data=data, timeout=120)
    if r.status_code == 403:
        _storage_key = None
        key = init_storage()
        r = requests.put(f"{STORAGE_URL}/objects/{path}",
                         headers={"X-Storage-Key": key, "Content-Type": content_type},
                         data=data, timeout=120)
    r.raise_for_status()
    return r.json()


def _get_object(path: str):
    global _storage_key
    key = init_storage()
    if not key:
        raise HTTPException(503, "Storage unavailable")
    r = requests.get(f"{STORAGE_URL}/objects/{path}",
                     headers={"X-Storage-Key": key}, timeout=60)
    if r.status_code == 403:
        _storage_key = None
        key = init_storage()
        r = requests.get(f"{STORAGE_URL}/objects/{path}",
                         headers={"X-Storage-Key": key}, timeout=60)
    r.raise_for_status()
    return r.content, r.headers.get("Content-Type", "application/octet-stream")


@router.post("/public/upload")
async def public_upload(file: UploadFile = File(...)):
    """Public image upload — used by the Sell/Wanted forms to attach property photos."""
    ct = (file.content_type or "").lower()
    if ct not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(400, "Only JPG, PNG or WebP images are allowed")
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(400, "Image exceeds 10 MB limit")
    if len(data) < 100:
        raise HTTPException(400, "Uploaded file is empty")
    ext = EXT_FROM_MIME[ct]
    file_id = new_id()
    path = f"{APP_NAME}/uploads/public/{file_id}.{ext}"
    result = _put_object(path, data, ct)
    await db.files.insert_one({
        "id": file_id, "storage_path": result["path"],
        "original_filename": file.filename, "content_type": ct,
        "size": result.get("size", len(data)), "is_deleted": False,
        "source": "public_upload", "created_at": now_iso(),
    })
    return {"id": file_id, "url": f"/api/files/{file_id}"}


@router.get("/files/{file_id}")
async def download_file(file_id: str):
    rec = await db.files.find_one({"id": file_id, "is_deleted": False}, {"_id": 0})
    if not rec:
        raise HTTPException(404, "File not found")
    data, ct = _get_object(rec["storage_path"])
    return Response(content=data, media_type=rec.get("content_type") or ct,
                    headers={"Cache-Control": "public, max-age=86400"})
