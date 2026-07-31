"""Cloudflare R2-backed public image upload and download."""

import logging
import os
from typing import Optional

import boto3
from botocore.client import BaseClient
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, File, HTTPException, Response, UploadFile

from core.db import db, new_id, now_iso

router = APIRouter()
logger = logging.getLogger("trel")

APP_NAME = "trel"

ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

EXT_FROM_MIME = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

_s3_client: Optional[BaseClient] = None


def _get_r2_config() -> dict:
    """Read Cloudflare R2 configuration from environment variables."""

    return {
        "access_key_id": os.getenv("R2_ACCESS_KEY_ID", "").strip(),
        "secret_access_key": os.getenv("R2_SECRET_ACCESS_KEY", "").strip(),
        "endpoint": os.getenv("R2_ENDPOINT", "").strip().rstrip("/"),
        "bucket": os.getenv("R2_BUCKET_NAME", "").strip(),
        "public_url": os.getenv(
            "R2_PUBLIC_URL",
            "https://images.trelpng.com",
        ).strip().rstrip("/"),
        "region": os.getenv("R2_REGION", "auto").strip() or "auto",
    }


def init_storage() -> Optional[BaseClient]:
    """Initialise and return the Cloudflare R2 S3-compatible client."""

    global _s3_client

    if _s3_client is not None:
        return _s3_client

    config = _get_r2_config()

    missing = [
        name
        for name, value in {
            "R2_ACCESS_KEY_ID": config["access_key_id"],
            "R2_SECRET_ACCESS_KEY": config["secret_access_key"],
            "R2_ENDPOINT": config["endpoint"],
            "R2_BUCKET_NAME": config["bucket"],
            "R2_PUBLIC_URL": config["public_url"],
        }.items()
        if not value
    ]

    if missing:
        logger.warning(
            "R2 storage unavailable. Missing environment variables: %s",
            ", ".join(missing),
        )
        return None

    try:
        _s3_client = boto3.client(
            "s3",
            endpoint_url=config["endpoint"],
            aws_access_key_id=config["access_key_id"],
            aws_secret_access_key=config["secret_access_key"],
            region_name=config["region"],
            config=Config(
                signature_version="s3v4",
                retries={
                    "max_attempts": 3,
                    "mode": "standard",
                },
            ),
        )

        logger.info(
            "Cloudflare R2 storage initialised for bucket %s",
            config["bucket"],
        )

        return _s3_client

    except Exception:
        logger.exception("Cloudflare R2 storage initialisation failed")
        _s3_client = None
        return None


def _public_url(path: str) -> str:
    """Create the public images.trelpng.com URL for an R2 object."""

    config = _get_r2_config()
    clean_path = path.lstrip("/")
    return f"{config['public_url']}/{clean_path}"


def _put_object(path: str, data: bytes, content_type: str) -> dict:
    """Upload an object to Cloudflare R2."""

    client = init_storage()

    if client is None:
        raise HTTPException(
            status_code=503,
            detail="Storage unavailable",
        )

    config = _get_r2_config()

    try:
        client.put_object(
            Bucket=config["bucket"],
            Key=path,
            Body=data,
            ContentType=content_type,
            CacheControl="public, max-age=31536000, immutable",
        )

        return {
            "path": path,
            "size": len(data),
            "url": _public_url(path),
        }

    except (ClientError, BotoCoreError):
        logger.exception("Cloudflare R2 upload failed for path %s", path)
        raise HTTPException(
            status_code=502,
            detail="Image upload failed",
        )

    except Exception:
        logger.exception(
            "Unexpected Cloudflare R2 upload error for path %s",
            path,
        )
        raise HTTPException(
            status_code=500,
            detail="Image upload failed",
        )


def _get_object(path: str):
    """Download an object directly from Cloudflare R2."""

    client = init_storage()

    if client is None:
        raise HTTPException(
            status_code=503,
            detail="Storage unavailable",
        )

    config = _get_r2_config()

    try:
        result = client.get_object(
            Bucket=config["bucket"],
            Key=path,
        )

        data = result["Body"].read()
        content_type = result.get(
            "ContentType",
            "application/octet-stream",
        )

        return data, content_type

    except ClientError as exc:
        error_code = str(
            exc.response.get("Error", {}).get("Code", "")
        )

        if error_code in {
            "NoSuchKey",
            "404",
            "NotFound",
        }:
            raise HTTPException(
                status_code=404,
                detail="File not found",
            )

        logger.exception(
            "Cloudflare R2 download failed for path %s",
            path,
        )
        raise HTTPException(
            status_code=502,
            detail="File download failed",
        )

    except (BotoCoreError, Exception):
        logger.exception(
            "Unexpected Cloudflare R2 download error for path %s",
            path,
        )
        raise HTTPException(
            status_code=500,
            detail="File download failed",
        )


@router.post("/public/upload")
async def public_upload(file: UploadFile = File(...)):
    """
    Upload an image to Cloudflare R2.

    This route is used by the website administration pages and public
    property forms.
    """

    content_type = (file.content_type or "").lower().strip()

    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Only JPG, PNG or WebP images are allowed",
        )

    data = await file.read()

    if not data or len(data) < 100:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty",
        )

    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400,
            detail="Image exceeds 10 MB limit",
        )

    extension = EXT_FROM_MIME[content_type]
    file_id = new_id()

    storage_path = (
        f"{APP_NAME}/uploads/public/"
        f"{file_id}.{extension}"
    )

    result = _put_object(
        path=storage_path,
        data=data,
        content_type=content_type,
    )

    record = {
        "id": file_id,
        "storage_path": result["path"],
        "public_url": result["url"],
        "original_filename": file.filename,
        "content_type": content_type,
        "size": result["size"],
        "is_deleted": False,
        "source": "public_upload",
        "created_at": now_iso(),
    }

    try:
        await db.files.insert_one(record)

    except Exception:
        logger.exception(
            "Image uploaded to R2 but database record creation failed: %s",
            storage_path,
        )
        raise HTTPException(
            status_code=500,
            detail="Image uploaded, but its database record could not be saved",
        )

    return {
        "ok": True,
        "id": file_id,
        "url": result["url"],
        "storage_path": result["path"],
        "size": result["size"],
        "content_type": content_type,
    }


@router.get("/files/{file_id}")
async def download_file(file_id: str):
    """Serve a previously uploaded file through the TREL API."""

    record = await db.files.find_one(
        {
            "id": file_id,
            "is_deleted": False,
        },
        {
            "_id": 0,
        },
    )

    if not record:
        raise HTTPException(
            status_code=404,
            detail="File not found",
        )

    data, detected_content_type = _get_object(
        record["storage_path"]
    )

    return Response(
        content=data,
        media_type=record.get("content_type")
        or detected_content_type,
        headers={
            "Cache-Control": "public, max-age=86400",
        },
    )
