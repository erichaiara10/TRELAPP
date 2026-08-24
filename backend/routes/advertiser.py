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


class ListingLifecyclePayload(BaseModel):
    status: str


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


@router.get("/listing-lifecycle")
async def listing_lifecycle(user: dict = Depends(get_current_user)):
    require_advertiser(user)
    rows = await db.advertiser_listing_lifecycle.find(
        {"user_id": user["id"]}, {"_id": 0}
    ).to_list(500)
    return {row["listing_id"]: row["status"] for row in rows}


@router.put("/listing-lifecycle/{listing_id}")
async def update_listing_lifecycle(
    listing_id: str,
    payload: ListingLifecyclePayload,
    user: dict = Depends(get_current_user),
):
    require_advertiser(user)
    allowed = {"Live", "Withdrawn", "Sold", "Leased", "Archived"}
    if payload.status not in allowed:
        raise HTTPException(400, "Invalid listing lifecycle status")
    timestamp = now_iso()
    await db.advertiser_listing_lifecycle.update_one(
        {"user_id": user["id"], "listing_id": listing_id},
        {"$set": {"status": payload.status, "updated_at": timestamp},
         "$setOnInsert": {
             "id": new_id(), "user_id": user["id"],
             "listing_id": listing_id, "created_at": timestamp,
         }},
        upsert=True,
    )
    await db.audit_events.insert_one({
        "id": new_id(), "action": "ADVERTISER_LISTING_LIFECYCLE_CHANGED",
        "subject_type": "advertiser_listing", "subject_id": listing_id,
        "actor_id": user["id"], "status": payload.status,
        "created_at": timestamp,
    })
    return {"ok": True, "listing_id": listing_id, "status": payload.status}
