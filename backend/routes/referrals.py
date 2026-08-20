"""Referral Partner submissions with the approved direct-owner rule."""
from fastapi import APIRouter, Depends, HTTPException

from core.account_policy import require_referral_partner
from core.db import db, new_id, now_iso
from models import PropertyReferralCreate

router = APIRouter()


@router.get("/referrals/mine")
async def my_referrals(user: dict = Depends(require_referral_partner)):
    return await db.property_referrals.find(
        {"referral_partner_id": user["id"]}, {"_id": 0}
    ).sort("referred_at", -1).to_list(500)


@router.post("/referrals")
async def create_referral(
    payload: PropertyReferralCreate,
    user: dict = Depends(require_referral_partner),
):
    # The Pydantic literals reject agent-sourced referrals and false/omitted
    # direct-owner declarations before any database write.
    if payload.source_relationship not in {"OWNER", "JOINT_OWNER"} or payload.direct_from_owner is not True:
        raise HTTPException(400, "Referral Partners may refer only properties sourced directly from the owner")
    record = {
        "id": new_id(),
        "property_id": payload.property_id,
        "referral_partner_id": user["id"],
        "owner_name": payload.owner_name.strip(),
        "owner_phone": payload.owner_phone,
        "owner_email": str(payload.owner_email) if payload.owner_email else None,
        "source_relationship": payload.source_relationship,
        "direct_from_owner": True,
        "is_original_referral": True,
        "status": "SUBMITTED",
        "notes": payload.notes or "",
        "referred_at": now_iso(),
    }
    if not record["owner_name"]:
        raise HTTPException(400, "Owner name is required")
    await db.property_referrals.insert_one(record)
    record.pop("_id", None)
    return record
