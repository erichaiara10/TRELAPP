"""Self-service Property Advertiser workspace endpoints."""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.account_policy import account_category, require_property_submitter
from core.db import db, new_id, now_iso
from core.property_advertising_rules import content_blockers, identity_values, status_token
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


@router.delete("/drafts/current")
async def delete_current_draft(user: dict = Depends(get_current_user)):
    """Delete only the advertiser's unfinished draft; never a Master Property."""
    require_advertiser(user)
    draft = await db.advertiser_drafts.find_one({"user_id": user["id"]}, {"_id": 0})
    if not draft:
        raise HTTPException(404, "No unfinished draft was found")
    await db.advertiser_drafts.delete_one({"id": draft["id"], "user_id": user["id"]})
    await db.audit_events.insert_one({
        "id": new_id(), "action": "ADVERTISER_DRAFT_DELETED",
        "subject_type": "advertiser_draft", "subject_id": draft["id"],
        "actor_id": user["id"], "previous_status": "DRAFT", "new_status": "DELETED",
        "reason": "Confirmed by advertiser", "created_at": now_iso(),
    })
    return {"ok": True, "deleted_draft_id": draft["id"]}


@router.post("/drafts/current/submit")
async def submit_draft(payload: DraftPayload, user: dict = Depends(require_property_submitter)):
    require_advertiser(user)
    blockers = content_blockers(payload.data)
    if blockers:
        raise HTTPException(400, {
            "code": "INCOMPLETE_PROPERTY_SUBMISSION",
            "message": "Complete the required property information before submitting",
            "blockers": blockers,
        })
    submitted_data = dict(payload.data)
    identity = identity_values(submitted_data)
    submitted_data["identity_scheme"] = identity["scheme"]
    submitted_data["identity_normalized"] = {
        key: sorted(value) if isinstance(value, set) else value
        for key, value in identity.items()
    }
    identifier = new_id()
    submission = {
        "id": identifier,
        "reference": f"TREL-{identifier[:8].upper()}",
        "user_id": user["id"],
        "data": submitted_data,
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
    existing = await db.advertiser_listing_lifecycle.find_one(
        {"user_id": user["id"], "listing_id": listing_id}, {"_id": 0}
    ) or {}
    current = status_token(existing.get("status") or "LIVE")
    requested = status_token(payload.status)
    allowed = {
        "LIVE": {"WITHDRAWN", "SOLD", "LEASED"},
        "WITHDRAWN": {"REACTIVATION_REQUESTED"},
        "SOLD": set(), "LEASED": set(), "ARCHIVED": set(),
    }
    if requested not in allowed.get(current, set()):
        raise HTTPException(409, f"Listing cannot move from {current} to {requested}")
    listing = await db.listings.find_one(
        {"$or": [{"id": listing_id}, {"property_id": listing_id}, {"listing_reference": listing_id}]},
        {"_id": 0},
    )
    if listing:
        master = await db.master_properties.find_one({"id": listing["property_id"]}, {"_id": 0, "created_by": 1}) or {}
        submission = await db.advertiser_submissions.find_one(
            {"integrated_listing_id": listing["id"], "user_id": user["id"]}, {"_id": 0, "reference": 1}
        )
        if master.get("created_by") != user["id"] and not submission:
            raise HTTPException(403, "This listing does not belong to your account")
    timestamp = now_iso()
    await db.advertiser_listing_lifecycle.update_one(
        {"user_id": user["id"], "listing_id": listing_id},
        {"$set": {"status": requested, "updated_at": timestamp},
         "$setOnInsert": {
             "id": new_id(), "user_id": user["id"],
             "listing_id": listing_id, "created_at": timestamp,
         }},
        upsert=True,
    )
    await db.audit_events.insert_one({
        "id": new_id(), "action": "ADVERTISER_LISTING_LIFECYCLE_CHANGED",
        "subject_type": "advertiser_listing", "subject_id": listing_id,
        "actor_id": user["id"], "previous_status": current,
        "new_status": requested, "status": requested,
        "created_at": timestamp,
    })
    if listing and requested in {"WITHDRAWN", "SOLD", "LEASED"}:
        integrated_status = requested.lower()
        await db.listings.update_one({"id": listing["id"]}, {"$set": {
            "publication_status": integrated_status, "responsible_channel_active": False,
            "updated_at": timestamp,
        }})
        await db.listing_status_history.insert_one({
            "id": new_id(), "listing_id": listing["id"], "status": integrated_status,
            "changed_at": timestamp, "changed_by": user["id"],
        })
        if submission:
            await db.staff_property_reviews.update_one(
                {"subject_ref": submission["reference"]},
                {"$set": {"publication_status": "UNPUBLISHED", "updated_at": timestamp}},
            )
    return {"ok": True, "listing_id": listing_id, "status": requested}
