"""Staff Property Advertising workspace APIs (S-series).

The collections are deliberately separate from the public property catalogue:
staff review must complete before a submission can create or alter a public
listing. Every workflow mutation also appends an immutable audit event.
"""
from copy import deepcopy
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo import ReturnDocument

from core.db import db, new_id, now_iso
from core.security import get_current_user, require_roles

router = APIRouter(prefix="/property-advertising", tags=["property-advertising"])
staff_user = require_roles("managing_director", "sales_agent", "leasing_agent", "marketing_officer")


ADVERTISERS = [
    ["ADV-00931", "John Tano", "Owner", "Verified", "Pending review", "3", "Today, 10:42am", "Active", "Eric Haiara"],
    ["ADV-00924", "Mary Kila", "Joint owner", "Verified", "Verified", "1", "18 Aug", "Active", "John Tom"],
    ["ADV-00872", "PNG Homes Ltd", "Authorised agent", "Verified", "Verified", "8", "17 Aug", "Active", "Rebecca Wali"],
    ["ADV-00841", "Peter Wali", "Authorised representative", "Email only", "Not started", "1", "02 Jul", "Incomplete", "Unassigned"],
]
SUBMISSIONS = [
    ["TREL-10428", "John's Family Home - Boroko", "John Tano", "Owner", "Advertise only", "18 Aug", "21 Aug", "Due today", "Clear", "Eric Haiara", "Under Review"],
    ["TREL-10461", "Family House - Waigani", "Mary Kila", "Owner", "TREL complete sale", "17 Aug", "20 Aug", "Due today", "Possible", "John Tom", "Conflict Review"],
    ["TREL-10422", "Two-Bedroom Unit - Boroko", "Lina Kora", "Landlord", "Find tenant only", "16 Aug", "19 Aug", "Overdue", "Clear", "Eric Haiara", "Information Required"],
    ["TREL-10376", "Vacant Land - 9 Mile", "Peter Wali", "Representative", "Advertise only", "15 Aug", "18 Aug", "Overdue", "Clear", "Rebecca Wali", "Ready"],
]
PUBLICATIONS = [
    ["LIST-10428", "John's Family Home - Boroko", "John Tano", "Sale", "Advertise only", "Approved", "Accepted", "Under review", "Required", "Ready", "Eric Haiara", "Draft"],
    ["LIST-10461", "Family House - Waigani", "Mary Kila", "Sale", "Complete sale", "Approved", "Accepted", "Verified", "None", "Blocked - conflict", "John Tom", "Changes Required"],
    ["LIST-10422", "Two-Bedroom Unit - Boroko", "Lina Kora", "Rent", "Find tenant only", "Approved", "Accepted", "Not submitted", "Shown", "Ready", "Eric Haiara", "Published"],
    ["LIST-10376", "Vacant Land - 9 Mile", "Peter Wali", "Sale", "Advertise only", "Approved", "Accepted", "Unable to verify", "Required", "Ready with disclosure", "John Tom", "Suspended"],
]
LOCATION_REQUESTS = [
    ["LOC-0081", "Sarah Kila", "John's Family Home - Boroko", "John Tano", "Buyer inspection", "18 Aug 10:21", "John Tano", "Pending", "Not shared", "Awaiting Advertiser"],
    ["LOC-0078", "PNG Bank Ltd", "Family House - Waigani", "Mary Kila", "Valuation", "17 Aug 14:10", "Mary Kila", "Share to 20 Aug", "Active", "Active"],
    ["LOC-0069", "Peter Wali", "Two-Bedroom Unit - Boroko", "Lina Kora", "Rental inspection", "15 Aug 11:32", "Lina Kora", "Inspection instead", "Not shared", "Closed"],
    ["LOC-0061", "Kila Moa", "Warehouse - Gordons", "TREL Staff", "Due diligence", "12 Aug 09:05", "Eric Haiara", "Share to 16 Aug", "Expired", "Expired"],
]
LIFECYCLE = [
    ["LIST-10428", "John's Family Home - Boroko", "John Tano", "Sale", "Advertise only", "Published", "Available", "14 Feb", "14 May", "17 Aug", "18 Aug", "0 months", "Confirmation Due", "Eric Haiara"],
    ["LIST-10361", "Family Home - Waigani", "Mary Kila", "Sale", "Complete sale", "Published", "Under Offer", "12 Jan", "12 May", "16 Aug", "12 Aug", "3 months", "Awaiting Advertiser", "John Tom"],
    ["LIST-10142", "Boroko Unit", "Lina Kora", "Rent", "Find tenant only", "Published", "Available", "18 Feb", "18 Feb", "18 Feb", "18 Aug", "6 months", "Six-Month Notice", "Eric Haiara"],
    ["LIST-09912", "Warehouse - Gordons", "PNG Homes Ltd", "Rent", "Advertise only", "Suspended", "Unknown", "10 Aug 2025", "10 Aug 2025", "10 Aug 2025", "10 Aug 2026", "12 months", "Removal Due", "Rebecca Wali"],
]

SEED = {
    "advertisers": ADVERTISERS,
    "submissions": SUBMISSIONS,
    "publications": PUBLICATIONS,
    "location_requests": LOCATION_REQUESTS,
    "lifecycle": LIFECYCLE,
}
COLLECTIONS = {
    "advertiser": "pa_advertisers",
    "submission": "pa_submissions",
    "publication": "pa_publications",
    "location_request": "pa_location_requests",
    "lifecycle": "pa_lifecycle",
}
STATUS_INDEX = {"advertiser": 7, "submission": 10, "publication": 11, "location_request": 9, "lifecycle": 12}
TRANSITIONS = {
    "advertiser": {"request_documents": "Documents Requested", "request_resubmission": "Resubmission Required", "reject_identity": "Restricted", "verify_identity": "Active"},
    "submission": {"request_clarification": "Information Required", "confirm_new_property": "Ready", "link_master_property": "Ready", "request_evidence": "Information Required", "hold_authority": "Authority On Hold", "accept_authority": "Ready", "return_for_changes": "Changes Required"},
    "publication": {"return": "Changes Required", "suspend": "Suspended", "unpublish": "Unpublished", "publish": "Published"},
    "location_request": {"send_to_advertiser": "Awaiting Advertiser", "request_information": "Information Required", "arrange_inspection": "Inspection Arranged", "decline": "Declined", "share_location": "Active"},
    "lifecycle": {"send_confirmation": "Awaiting Advertiser", "record_response": "Current", "suspend": "Suspended", "archive": "Archived"},
}
NOTIFY_ACTIONS = {
    "request_documents", "request_resubmission", "request_clarification",
    "request_evidence", "send_to_advertiser", "request_information",
    "send_confirmation",
}


class WorkflowAction(BaseModel):
    record_type: Literal["advertiser", "submission", "publication", "location_request", "lifecycle"]
    reference: str = Field(min_length=3, max_length=80)
    action: str = Field(min_length=2, max_length=80)
    reason: Optional[str] = Field(default=None, max_length=1000)


class AdvertiserDraftIn(BaseModel):
    data: dict
    current_step: int = Field(default=1, ge=1, le=5)


def require_advertiser(user: dict):
    if user.get("role") not in {"property_advertiser", "advertiser"}:
        raise HTTPException(403, "A Property Advertiser account is required")


async def next_reference(counter: str, prefix: str, start: int) -> str:
    await db.pa_counters.update_one(
        {"_id": counter}, {"$setOnInsert": {"value": start}}, upsert=True,
    )
    result = await db.pa_counters.find_one_and_update(
        {"_id": counter}, {"$inc": {"value": 1}},
        return_document=ReturnDocument.AFTER,
    )
    return f"{prefix}{result['value']:05d}"


async def ensure_advertiser(user: dict) -> dict:
    existing = await db.pa_advertisers.find_one({"owner_user_id": user["id"]}, {"_id": 0})
    if existing:
        return existing
    reference = await next_reference("advertiser", "ADV-", 10000)
    row = [reference, user.get("name") or user.get("email"), "Owner", "Verified", "Not started", "0", "Today", "Active", "Unassigned"]
    doc = {"id": new_id(), "reference": reference, "owner_user_id": user["id"], "email": user.get("email"), "row": row, "created_at": now_iso(), "updated_at": now_iso()}
    await db.pa_advertisers.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


def validate_submission(data: dict):
    required = {
        "listing_type": "Sale or Rent", "service": "TREL service", "relationship": "Relationship",
        "property_class": "Property category", "property_type": "Property type",
        "title": "Property title", "price": "Price", "description": "Description",
        "province": "Province", "city": "City / Town", "suburb": "Suburb",
        "section": "Section number", "lot": "Lot number",
    }
    missing = [label for key, label in required.items() if not str(data.get(key) or "").strip()]
    if missing:
        raise HTTPException(400, f"Complete these required fields: {', '.join(missing)}")
    price = str(data.get("price", "")).replace("PGK", "").replace(",", "").strip()
    try:
        if float(price) <= 0:
            raise ValueError
    except ValueError:
        raise HTTPException(400, "Price must be greater than zero")
    if not data.get("authority_confirmed") or not data.get("terms_accepted"):
        raise HTTPException(400, "Both declarations must be accepted before submission")


@router.get("/advertiser/me")
async def advertiser_me(user: dict = Depends(get_current_user)):
    require_advertiser(user)
    return await ensure_advertiser(user)


@router.get("/advertiser/drafts/current")
async def current_draft(user: dict = Depends(get_current_user)):
    require_advertiser(user)
    await ensure_advertiser(user)
    return await db.pa_drafts.find_one({"owner_user_id": user["id"], "status": "draft"}, {"_id": 0})


@router.put("/advertiser/drafts/current")
async def save_draft(payload: AdvertiserDraftIn, user: dict = Depends(get_current_user)):
    require_advertiser(user)
    advertiser = await ensure_advertiser(user)
    now = now_iso()
    existing = await db.pa_drafts.find_one({"owner_user_id": user["id"], "status": "draft"}, {"_id": 0})
    if existing:
        await db.pa_drafts.update_one({"id": existing["id"], "owner_user_id": user["id"]}, {"$set": {"data": payload.data, "current_step": payload.current_step, "updated_at": now}})
        draft_id = existing["id"]
    else:
        draft_id = new_id()
        await db.pa_drafts.insert_one({"id": draft_id, "owner_user_id": user["id"], "advertiser_reference": advertiser["reference"], "status": "draft", "data": payload.data, "current_step": payload.current_step, "created_at": now, "updated_at": now})
    return await db.pa_drafts.find_one({"id": draft_id}, {"_id": 0})


@router.post("/advertiser/drafts/current/submit")
async def submit_draft(payload: AdvertiserDraftIn, user: dict = Depends(get_current_user)):
    require_advertiser(user)
    validate_submission(payload.data)
    advertiser = await ensure_advertiser(user)
    saved = await save_draft(payload, user)
    reference = await next_reference("submission", "TREL-", 11000)
    now = now_iso()
    d = payload.data
    row = [reference, d["title"], user.get("name") or user.get("email"), d["relationship"], d["service"], "Today", "Within 3 days", "On time", "Pending check", "Unassigned", "Submitted"]
    submission = {"id": new_id(), "reference": reference, "owner_user_id": user["id"], "advertiser_reference": advertiser["reference"], "draft_id": saved["id"], "data": d, "row": row, "status": "Submitted", "created_at": now, "updated_at": now}
    await db.pa_submissions.insert_one(submission)
    await db.pa_drafts.update_one({"id": saved["id"], "owner_user_id": user["id"]}, {"$set": {"status": "submitted", "submission_reference": reference, "updated_at": now}})
    await db.pa_advertisers.update_one({"owner_user_id": user["id"]}, {"$inc": {"submission_count": 1}, "$set": {"updated_at": now}})
    await db.pa_audit.insert_one({"id": new_id(), "record_type": "submission", "reference": reference, "action": "submit", "previous_status": "Draft", "new_status": "Submitted", "reason": "Advertiser submitted property", "performed_by_id": user["id"], "performed_by_name": user.get("name") or user.get("email"), "channel": "advertiser_workspace", "created_at": now})
    return {k: v for k, v in submission.items() if k != "_id"}


@router.get("/advertiser/submissions")
async def advertiser_submissions(user: dict = Depends(get_current_user)):
    require_advertiser(user)
    return await db.pa_submissions.find({"owner_user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(500)


async def ensure_seeded():
    """Create representative dev records once; never overwrite real changes."""
    for key, rows in SEED.items():
        collection = db[f"pa_{key}"]
        for row in rows:
            await collection.update_one(
                {"reference": row[0]},
                {"$setOnInsert": {"id": new_id(), "reference": row[0], "row": deepcopy(row), "created_at": now_iso(), "updated_at": now_iso()}},
                upsert=True,
            )


async def rows(collection_name: str):
    docs = await db[collection_name].find({}, {"_id": 0}).sort("created_at", 1).to_list(1000)
    return [doc["row"] for doc in docs]


@router.get("/workspace")
async def workspace(user: dict = Depends(staff_user)):
    await ensure_seeded()
    return {
        "advertisers": await rows("pa_advertisers"),
        "submissions": await rows("pa_submissions"),
        "publications": await rows("pa_publications"),
        "location_requests": await rows("pa_location_requests"),
        "lifecycle": await rows("pa_lifecycle"),
    }


@router.get("/{record_type}/{reference}")
async def get_record(record_type: str, reference: str, user: dict = Depends(staff_user)):
    await ensure_seeded()
    collection_name = COLLECTIONS.get(record_type)
    if not collection_name:
        raise HTTPException(404, "Unknown property-advertising record type")
    doc = await db[collection_name].find_one({"reference": reference}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Property-advertising record not found")
    doc["audit"] = await db.pa_audit.find({"record_type": record_type, "reference": reference}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return doc


@router.post("/actions")
async def apply_action(payload: WorkflowAction, user: dict = Depends(staff_user)):
    await ensure_seeded()
    new_status = TRANSITIONS[payload.record_type].get(payload.action)
    if not new_status:
        raise HTTPException(400, "Action is not allowed for this record type")
    collection = db[COLLECTIONS[payload.record_type]]
    doc = await collection.find_one({"reference": payload.reference}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Property-advertising record not found")
    row = list(doc["row"])
    status_index = STATUS_INDEX[payload.record_type]
    previous_status = row[status_index]
    row[status_index] = new_status
    timestamp = now_iso()
    result = await collection.update_one(
        {"reference": payload.reference, "updated_at": doc["updated_at"]},
        {"$set": {"row": row, "status": new_status, "updated_at": timestamp}},
    )
    if result.modified_count != 1:
        raise HTTPException(409, "Record changed while you were reviewing it; refresh and retry")
    audit = {
        "id": new_id(), "record_type": payload.record_type, "reference": payload.reference,
        "action": payload.action, "previous_status": previous_status, "new_status": new_status,
        "reason": payload.reason or "", "performed_by_id": user["id"],
        "performed_by_name": user.get("name") or user.get("email"), "channel": "staff_workspace",
        "created_at": timestamp,
    }
    await db.pa_audit.insert_one(audit)
    if payload.action in NOTIFY_ACTIONS:
        await db.pa_notifications.insert_one({
            "id": new_id(), "record_type": payload.record_type,
            "reference": payload.reference, "action": payload.action,
            "status": "queued", "channels": ["inbox", "email"],
            "requested_by_id": user["id"], "recipient_user_id": doc.get("owner_user_id"),
            "created_at": timestamp,
        })
    return {"ok": True, "record": {**doc, "row": row, "updated_at": timestamp}, "audit": {k: v for k, v in audit.items() if k != "_id"}}


@router.get("/audit-events")
async def audit_events(limit: int = 200, user: dict = Depends(staff_user)):
    limit = max(1, min(limit, 1000))
    return await db.pa_audit.find({}, {"_id": 0}).sort("created_at", -1).to_list(limit)


@router.get("/notification-outbox")
async def notification_outbox(limit: int = 200, user: dict = Depends(staff_user)):
    """Read-only staff view of notifications queued for the delivery service."""
    limit = max(1, min(limit, 1000))
    return await db.pa_notifications.find({}, {"_id": 0}).sort("created_at", -1).to_list(limit)
