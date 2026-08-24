"""Self-service Property Advertiser workspace endpoints."""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.account_policy import account_category, require_property_writer
from core.db import db, new_id, now_iso
from core.security import get_current_user

router = APIRouter(prefix="/property-advertising/advertiser")


class DraftPayload(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)
    current_step: int = Field(default=1, ge=1, le=5)


def require_advertiser(user: dict) -> None:
    if account_category(user) != "PROPERTY_ADVERTISER":
        raise HTTPException(403, "Property Advertiser account required")


@router.get("/drafts/current")
async def current_draft(user: dict = Depends(get_current_user)):
    require_advertiser(user)
    return await db.advertiser_drafts.find_one(
        {"user_id": user["id"]}, {"_id": 0}
    ) or {"data": {}, "current_step": 1}


@router.put("/drafts/current")
async def save_draft(payload: DraftPayload, user: dict = Depends(get_current_user)):
    require_advertiser(user)
    saved = {
        "user_id": user["id"], "data": payload.data,
        "current_step": payload.current_step, "updated_at": now_iso(),
    }
    await db.advertiser_drafts.update_one(
        {"user_id": user["id"]},
        {"$set": saved, "$setOnInsert": {"id": new_id(), "created_at": now_iso()}},
        upsert=True,
    )
    return {**saved, "ok": True}


@router.post("/drafts/current/submit")
async def submit_draft(payload: DraftPayload, user: dict = Depends(require_property_writer)):
    require_advertiser(user)
    title = str(payload.data.get("title") or "").strip()
    description = str(payload.data.get("description") or "").strip()
    if not title or not description:
        raise HTTPException(400, "Property title and description are required")
    identifier = new_id()
    submission = {
        "id": identifier,
        "reference": f"TREL-{identifier[:8].upper()}",
        "user_id": user["id"],
        "data": payload.data,
        "status": "Under Review",
        "submitted_at": now_iso(),
    }
    await db.advertiser_submissions.insert_one(submission)
    await db.advertiser_drafts.delete_one({"user_id": user["id"]})
    submission.pop("_id", None)
    return submission


@router.get("/submissions")
async def submissions(user: dict = Depends(get_current_user)):
    require_advertiser(user)
    return await db.advertiser_submissions.find(
        {"user_id": user["id"]}, {"_id": 0}
    ).sort("submitted_at", -1).to_list(500)
