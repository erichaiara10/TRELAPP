"""Staff Property Advertising workspace APIs (S-series).

The collections are deliberately separate from the public property catalogue:
staff review must complete before a submission can create or alter a public
listing. Every workflow mutation also appends an immutable audit event.
"""
from copy import deepcopy
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.db import db, new_id, now_iso
from core.security import require_roles

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
        {"$set": {"row": row, "updated_at": timestamp}},
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
            "requested_by_id": user["id"], "created_at": timestamp,
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
