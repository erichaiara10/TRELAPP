"""Public entry points for approved Property Advertising listings."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field

from core.db import db, new_id, now_iso
from core.security import captcha_verify, honeypot_check


router = APIRouter(prefix="/property-advertising")


class ExactLocationRequestIn(BaseModel):
    property_id: str = Field(min_length=2, max_length=120)
    requester_name: str = Field(min_length=2, max_length=160)
    requester_email: EmailStr
    requester_phone: Optional[str] = Field(default=None, max_length=50)
    reason: str = Field(min_length=3, max_length=500)
    message: Optional[str] = Field(default=None, max_length=2000)
    verification_token: Optional[str] = None
    verification_answer: Optional[str] = None
    hp_website: Optional[str] = None


@router.post("/location-requests", status_code=201)
async def request_exact_location(payload: ExactLocationRequestIn):
    honeypot_check(payload.hp_website)
    captcha_verify(payload.verification_token, payload.verification_answer)
    listing = await db.listings.find_one(
        {"$or": [{"id": payload.property_id}, {"property_id": payload.property_id}],
         "publication_status": "active", "responsible_channel_active": True},
        {"_id": 0},
    )
    if not listing:
        raise HTTPException(404, "Published property not found")
    property_id = listing["property_id"]
    master = await db.master_properties.find_one({"id": property_id}, {"_id": 0}) or {}
    address = await db.property_addresses.find_one(
        {"property_id": property_id, "is_canonical": True, "valid_to": None}, {"_id": 0}
    ) or {}
    review = await db.staff_property_reviews.find_one(
        {"listing_reference": listing.get("listing_reference")}, {"_id": 0}
    ) or {}
    submission = await db.advertiser_submissions.find_one(
        {"reference": review.get("subject_ref")}, {"_id": 0}
    ) or {}
    advertiser = await db.users.find_one(
        {"id": submission.get("user_id") or master.get("created_by")},
        {"_id": 0, "password_hash": 0},
    ) or {}
    data = submission.get("data") or {}
    advertise_only = str(data.get("service") or listing.get("service") or "").strip().lower() == "advertise only"
    identifier = new_id()
    reference = f"LOC-{identifier[:8].upper()}"
    record = {
        "id": identifier,
        "reference": reference,
        "property_id": property_id,
        "listing_id": listing["id"],
        "listing_reference": listing.get("listing_reference"),
        "submission_reference": submission.get("reference"),
        "property_title": listing.get("title") or master.get("title") or "Property",
        "advertiser_id": advertiser.get("id"),
        "advertiser_reference": advertiser.get("advertiser_reference"),
        "advertiser_name": advertiser.get("name"),
        "requester_name": payload.requester_name.strip(),
        "requester_email": str(payload.requester_email).lower(),
        "requester_phone": payload.requester_phone,
        "contact_verified": False,
        "reason": payload.reason.strip(),
        "message": payload.message,
        "decision_authority": "ADVERTISER" if advertise_only else "STAFF",
        "advertiser_consent_status": "PENDING" if advertise_only else "NOT_REQUIRED",
        "status": "AWAITING_ADVERTISER" if advertise_only else "PENDING",
        "exact_location": {
            "street_address": address.get("street_address"),
            "map_coords": address.get("map_coords"),
            "nearby_landmark": address.get("nearby_landmark"),
        },
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.exact_location_requests.insert_one(record)
    await db.audit_events.insert_one({
        "id": new_id(), "action": "EXACT_LOCATION_REQUESTED",
        "subject_type": "exact_location_request", "subject_id": reference,
        "actor_id": None, "new_status": record["status"],
        "reason": record["reason"], "created_at": now_iso(),
    })
    return {"ok": True, "reference": reference, "status": record["status"]}
