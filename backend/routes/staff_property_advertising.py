"""Staff operations for Property Advertiser accounts and listing workflows.

The advertiser workspace owns draft/submission creation.  This router exposes
the same records to active staff and stores review decisions, publication,
lifecycle state and immutable audit events.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import re
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field

from core.account_policy import require_staff
from core.db import client, db, new_id, now_iso
from core.integrated_property_service import (
    DuplicatePropertyError,
    IntegratedPropertyService,
    PartialWriteError,
)
from core.notify import notify
from core.property_advertising_rules import (
    content_blockers,
    add_months,
    duplicate_identity_match,
    identity_reasons,
    identity_scheme,
    identity_values,
    lifecycle_action_allowed,
    lifecycle_filter_match,
    lifecycle_transition,
    lifecycle_deadlines,
    normalize_candidates,
    optional_number,
    price_label,
    parse_datetime,
    publication_transition,
    status_token,
    submission_sla,
)
from routes.files import _get_object


router = APIRouter(prefix="/property-advertising/staff")

FULL_CONTROL = {"system_admin", "managing_director"}
CAPABILITY_ROLES = {
    "account_management": FULL_CONTROL,
    "identity": FULL_CONTROL,
    "submission": FULL_CONTROL | {"sales_manager", "sales_agent", "leasing_agent", "property_manager"},
    "authority": FULL_CONTROL | {"sales_manager", "property_manager"},
    "publication": FULL_CONTROL | {"sales_manager", "marketing_officer"},
    "lifecycle": FULL_CONTROL | {"sales_manager", "sales_agent", "leasing_agent", "property_manager", "marketing_officer"},
}


async def ensure_indexes() -> None:
    await db.staff_property_reviews.create_index("subject_ref", unique=True)
    await db.advertiser_submissions.create_index("reference", sparse=True)
    await db.advertiser_submissions.create_index([
        ("data.identity_normalized.scheme", 1),
        ("data.identity_normalized.allotment", 1),
        ("data.identity_normalized.section", 1),
    ], name="ix_advertiser_serviced_identity", sparse=True)
    await db.advertiser_submissions.create_index([
        ("data.identity_normalized.scheme", 1),
        ("data.identity_normalized.portion", 1),
    ], name="ix_advertiser_portion_identity", sparse=True)
    await db.advertiser_submissions.create_index("data.identity_normalized.localities",
                                                  name="ix_advertiser_identity_localities", sparse=True)
    await db.advertiser_listing_lifecycle.create_index(
        [("user_id", 1), ("listing_id", 1)], unique=True,
        name="ux_advertiser_listing_lifecycle",
    )
    await db.advertiser_listing_lifecycle.create_index("next_due", sparse=True)
    await db.advertiser_listing_lifecycle.create_index("unpublish_due", sparse=True)
    await db.advertiser_listing_lifecycle.create_index("archive_due", sparse=True)


class DecisionIn(BaseModel):
    action: str = Field(min_length=2, max_length=60)
    reason: str = Field(min_length=3, max_length=1000)
    notes: Optional[str] = Field(default=None, max_length=2000)


class LifecycleDecisionIn(DecisionIn):
    availability: Optional[Literal["AVAILABLE", "UNDER_OFFER", "SOLD", "LEASED", "WITHDRAWN"]] = None
    price_confirmed: Optional[bool] = None
    description_confirmed: Optional[bool] = None
    photos_confirmed: Optional[bool] = None
    contact_confirmed: Optional[bool] = None
    inspection_confirmed: Optional[bool] = None


class ConflictDecisionIn(DecisionIn):
    master_property_id: Optional[str] = Field(default=None, max_length=120)


class ContactVerificationIn(DecisionIn):
    channel: Literal["EMAIL", "MOBILE"]


class AdvertiserManagementIn(DecisionIn):
    assigned_staff_id: Optional[str] = Field(default=None, max_length=120)


def _clean(document: Optional[dict]) -> dict:
    result = dict(document or {})
    result.pop("_id", None)
    result.pop("password_hash", None)
    result.pop("storage_path", None)
    return result


def _advertiser_reference(user: dict) -> str:
    explicit = str(user.get("advertiser_reference") or "").strip()
    if explicit:
        return explicit
    token = "".join(ch for ch in str(user.get("id", "")) if ch.isalnum()).upper()[:8]
    return f"ADV-{token or 'UNKNOWN'}"


def _listing_reference(submission: dict, review: dict) -> str:
    explicit = str(review.get("listing_reference") or submission.get("listing_reference") or "").strip()
    if explicit:
        return explicit
    reference = str(submission.get("reference") or submission.get("id") or "")
    suffix = reference.split("-", 1)[-1]
    return f"LIST-{suffix}"


def _display_date(value: Any) -> str:
    if not value:
        return "—"
    return str(value)


def _identity_signature(data: dict) -> str:
    identity = identity_values(data)
    serializable = {
        key: sorted(value) if isinstance(value, set) else value
        for key, value in identity.items()
    }
    return json.dumps(serializable, sort_keys=True, separators=(",", ":"))


def _require_capability(user: dict, capability: str) -> None:
    if str(user.get("role") or "") not in CAPABILITY_ROLES[capability]:
        raise HTTPException(403, f"Your Staff role cannot perform {capability} decisions")


def _capabilities(user: dict) -> dict[str, bool]:
    role = str(user.get("role") or "")
    return {name: role in roles for name, roles in CAPABILITY_ROLES.items()}


async def _audit(user: dict, subject_type: str, subject_id: str, action: str,
                 previous_status: Optional[str], new_status: Optional[str],
                 reason: str, notes: Optional[str] = None, metadata: Optional[dict] = None) -> dict:
    event = {
        "id": new_id(), "action": action, "subject_type": subject_type,
        "subject_id": subject_id, "actor_id": user["id"],
        "actor_name": user.get("name") or user.get("email"),
        "actor_role": user.get("role"), "previous_status": previous_status,
        "new_status": new_status, "reason": reason, "notes": notes,
        "metadata": metadata or {}, "created_at": now_iso(),
    }
    await db.audit_events.insert_one(event.copy())
    return event


async def _reviews() -> dict[str, dict]:
    rows = await db.staff_property_reviews.find({}, {"_id": 0}).to_list(5000)
    return {row["subject_ref"]: row for row in rows if row.get("subject_ref")}


async def _advertiser_users() -> list[dict]:
    return await db.users.find(
        {"account_category": "PROPERTY_ADVERTISER"},
        {"_id": 0, "password_hash": 0},
    ).sort("created_at", -1).to_list(1000)


async def _find_advertiser(reference: str) -> dict:
    for user in await _advertiser_users():
        if reference in {user.get("id"), _advertiser_reference(user)}:
            return user
    raise HTTPException(404, "Advertiser not found")


async def _find_submission(reference: str) -> dict:
    row = await db.advertiser_submissions.find_one(
        {"$or": [{"reference": reference}, {"id": reference}]}, {"_id": 0}
    )
    if not row:
        raise HTTPException(404, "Submission not found")
    return row


async def _master_identity_records() -> list[dict]:
    records = []
    parcels = await db.property_parcels.find({}, {"_id": 0}).to_list(5000)
    for parcel in parcels:
        property_id = parcel.get("property_id")
        if not property_id:
            continue
        address = await db.property_addresses.find_one(
            {"property_id": property_id, "valid_to": None}, {"_id": 0}
        ) or await db.property_addresses.find_one({"property_id": property_id}, {"_id": 0}) or {}
        master = await db.master_properties.find_one(
            {"id": property_id}, {"_id": 0, "id": 1, "title": 1}
        ) or {}
        records.append({
            "id": property_id,
            "title": master.get("title") or "Existing Master Property",
            "data": {
                "identity_scheme": "LARGE_PORTION" if parcel.get("identifier_scheme") in {"PORTION", "CUSTOMARY"} else "SERVICED",
                "portion": parcel.get("portion"),
                "location": parcel.get("location_norm") or address.get("district_name"),
                "city": address.get("city_name"),
                "lot": parcel.get("lot"),
                "section": parcel.get("section"),
                "street": address.get("street_name") or parcel.get("street_norm"),
                "suburb": address.get("suburb_name"),
            },
        })
    return records


async def _duplicate_candidates(
    row: dict,
    submissions: Optional[list[dict]] = None,
    master_records: Optional[list[dict]] = None,
) -> list[dict]:
    """Find exact identity matches in submissions and durable Master Properties."""
    data = row.get("data") or {}
    candidates: list[dict] = []
    other_submissions = submissions
    if other_submissions is None:
        other_submissions = await db.advertiser_submissions.find(
            {"id": {"$ne": row.get("id")}}, {"_id": 0}
        ).to_list(5000)
    for candidate in other_submissions:
        if candidate.get("id") == row.get("id"):
            continue
        if duplicate_identity_match(data, candidate.get("data") or {}):
            candidates.append({
                "source": "SUBMISSION",
                "id": candidate.get("id"),
                "reference": candidate.get("reference") or candidate.get("id"),
                "title": (candidate.get("data") or {}).get("title") or "Existing submission",
                "reasons": identity_reasons(data),
            })

    master_records = master_records if master_records is not None else await _master_identity_records()
    linked_master_id = str(row.get("master_property_id") or "").strip()
    for master in master_records:
        property_id = master["id"]
        # Once publication creates or links the durable Master Property, that
        # record is the submission's identity—not a competing duplicate.
        if linked_master_id and property_id == linked_master_id:
            continue
        if duplicate_identity_match(data, master["data"]):
            candidates.append({
                "source": "MASTER_PROPERTY",
                "id": property_id,
                "property_id": property_id,
                "reference": property_id,
                "title": master["title"],
                "reasons": identity_reasons(data),
            })
    return normalize_candidates(candidates)


async def _advertiser_summary(user: dict) -> dict:
    reference = _advertiser_reference(user)
    profile = _clean(await db.advertiser_profiles.find_one({"user_id": user["id"]}, {"_id": 0}))
    documents = await db.identity_documents.find(
        {"user_id": user["id"]}, {"_id": 0, "storage_path": 0, "url": 0}
    ).sort("created_at", -1).to_list(20)
    submission_count = await db.advertiser_submissions.count_documents({"user_id": user["id"]})
    identity_status = "NOT_STARTED"
    if documents:
        statuses = {str(item.get("status", "")).upper() for item in documents}
        identity_status = "VERIFIED" if "VERIFIED" in statuses else "REJECTED" if statuses == {"REJECTED"} else "PENDING_REVIEW"
    return {
        "reference": reference, "id": user["id"], "name": user.get("name") or "Unnamed advertiser",
        "email": user.get("email"), "phone": user.get("phone"),
        "email_verified": bool(user.get("email_verified") or user.get("google_email_verified")),
        "mobile_verified": bool(user.get("mobile_verified") or user.get("phone_verified")),
        "account_status": user.get("status", "ACTIVE"), "role": user.get("role"),
        "relationship": profile.get("relationship_type") or "NOT_SET",
        "profile_status": profile.get("status") or "INCOMPLETE",
        "identity_status": identity_status, "property_count": submission_count,
        "last_active": user.get("last_login_at") or user.get("updated_at") or user.get("created_at"),
        "assigned_staff": profile.get("assigned_staff_name") or "Unassigned",
    }


async def _submission_summary(
    row: dict,
    reviews: Optional[dict[str, dict]] = None,
    submissions: Optional[list[dict]] = None,
    master_records: Optional[list[dict]] = None,
) -> dict:
    reviews = reviews or await _reviews()
    reference = row.get("reference") or row.get("id")
    data = row.get("data") or {}
    review = reviews.get(reference, {})
    advertiser = await db.users.find_one({"id": row.get("user_id")}, {"_id": 0, "password_hash": 0}) or {}
    profile = await db.advertiser_profiles.find_one({"user_id": row.get("user_id")}, {"_id": 0}) or {}
    candidates = await _duplicate_candidates(row, submissions, master_records)
    conflict_status = review.get("conflict_status")
    signature = _identity_signature(data)
    stored_signature = review.get("conflict_identity_signature")
    resolved_statuses = {"CLARIFICATION_REQUESTED", "NEW_PROPERTY_CONFIRMED", "LINKED_TO_MASTER"}
    stale_resolution = bool(
        (stored_signature is not None and stored_signature != signature)
        or (stored_signature is None and conflict_status in resolved_statuses)
    )
    if stale_resolution:
        conflict_status = "POSSIBLE" if candidates else "CLEAR"
        await db.staff_property_reviews.update_one(
            {"subject_ref": reference},
            {"$set": {"conflict_status": conflict_status,
                      "conflict_identity_signature": signature,
                      "conflict_resolution_stale": True,
                      "updated_at": now_iso()},
             "$unset": {"master_property_id": ""}},
        )
        await db.advertiser_submissions.update_one(
            {"id": row.get("id")}, {"$unset": {"master_property_id": ""}, "$set": {"updated_at": now_iso()}},
        )
    if not conflict_status:
        conflict_status = "POSSIBLE" if candidates else "CLEAR"
    submission_status = review.get("submission_status") or row.get("status") or "UNDER_REVIEW"
    calculated_due, calculated_sla = submission_sla(row.get("submitted_at"), submission_status)
    return {
        "reference": reference, "id": row.get("id"), "user_id": row.get("user_id"),
        "property_title": data.get("title") or "Untitled property",
        "advertiser_name": advertiser.get("name") or "Unknown advertiser",
        "advertiser_reference": _advertiser_reference(advertiser) if advertiser else None,
        "relationship": data.get("relationship") or profile.get("relationship_type") or "NOT_SET",
        "service": data.get("service") or "NOT_SET", "submitted_at": row.get("submitted_at"),
        "review_due": review.get("review_due") or calculated_due,
        "sla": review.get("sla") or calculated_sla,
        "conflict_status": conflict_status, "duplicate_candidates": candidates,
        "conflict_resolution_stale": stale_resolution or bool(review.get("conflict_resolution_stale")),
        "master_property_id": review.get("master_property_id") or row.get("master_property_id"),
        "authority_status": review.get("authority_status") or "PENDING",
        "assigned_staff": review.get("assigned_staff_name") or "Unassigned",
        "status": submission_status,
        "listing_reference": _listing_reference(row, review), "price_label": price_label(data),
        "content_blockers": content_blockers(data), "data": data,
    }


async def _submission_summaries(rows: list[dict], reviews: Optional[dict[str, dict]] = None) -> list[dict]:
    reviews = reviews or await _reviews()
    master_records = await _master_identity_records()
    return [await _submission_summary(row, reviews, rows, master_records) for row in rows]


async def _submission_detail(reference: str) -> dict:
    row = await _find_submission(reference)
    reviews = await _reviews()
    result = await _submission_summary(row, reviews)
    user_id = row.get("user_id")
    documents = await db.files.find(
        {"uploaded_by": user_id, "source": "property_document", "is_deleted": False},
        {"_id": 0, "storage_path": 0, "public_url": 0},
    ).sort("created_at", -1).to_list(100)
    identity_documents = await db.identity_documents.find(
        {"user_id": user_id}, {"_id": 0, "storage_path": 0, "url": 0}
    ).sort("created_at", -1).to_list(20)
    audit = await db.audit_events.find(
        {"subject_id": {"$in": [reference, result["listing_reference"]]}}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    result.update({
        "documents": documents, "identity_documents": identity_documents,
        "review": reviews.get(reference, {}), "audit": audit,
    })
    return result


def _page(items: list[dict], page: int, limit: int) -> dict:
    total = len(items)
    start = (page - 1) * limit
    return {"items": items[start:start + limit], "total": total, "page": page, "limit": limit}


@router.get("/overview")
async def overview(user: dict = Depends(require_staff)):
    advertisers = await _advertiser_users()
    submissions = await db.advertiser_submissions.count_documents({})
    pending_identity = await db.identity_documents.count_documents({"status": {"$in": ["PENDING", "PENDING_REVIEW", "UNDER_REVIEW"]}})
    publication_ready = sum(1 for item in await _publication_items() if item["readiness"] == "READY")
    priorities = await db.staff_property_tasks.find({"status": {"$ne": "COMPLETED"}}, {"_id": 0}).sort("due_at", 1).to_list(50)
    if not priorities:
        pending_documents = await db.identity_documents.find(
            {"status": {"$in": ["PENDING", "PENDING_REVIEW", "UNDER_REVIEW"]}}, {"_id": 0}
        ).sort("created_at", 1).to_list(10)
        for document in pending_documents:
            advertiser = await db.users.find_one({"id": document.get("user_id")}, {"_id": 0, "password_hash": 0}) or {}
            priorities.append({"id": document.get("id"), "priority": "HIGH", "task": "Identity review",
                "subject_label": advertiser.get("name") or "Property advertiser", "assigned_staff_name": "Unassigned",
                "due_at": document.get("created_at"), "path": f"/admin/property-advertising/advertisers/{_advertiser_reference(advertiser)}/identity"})
        pending_submissions = await db.advertiser_submissions.find(
            {"status": {"$nin": ["APPROVED", "REJECTED"]}}, {"_id": 0}
        ).sort("submitted_at", 1).to_list(10)
        for submission in pending_submissions:
            due_at, sla = submission_sla(submission.get("submitted_at"), submission.get("status"))
            priorities.append({"id": submission.get("id"), "priority": "NORMAL", "task": "Submission review",
                "subject_label": (submission.get("data") or {}).get("title") or submission.get("reference"),
                "assigned_staff_name": "Unassigned", "due_at": due_at,
                "sla": sla,
                "path": f"/admin/property-advertising/submissions/{submission.get('reference')}"})
    return {
        "stats": {"advertisers": len(advertisers), "submissions": submissions,
                  "pending_identity": pending_identity, "ready_to_publish": publication_ready},
        "priorities": priorities,
    }


@router.get("/capabilities")
async def capabilities(user: dict = Depends(require_staff)):
    return {"role": user.get("role"), "capabilities": _capabilities(user)}


@router.get("/advertisers")
async def advertisers(q: str = "", status: str = "", page: int = Query(1, ge=1),
                      limit: int = Query(25, ge=1, le=100), user: dict = Depends(require_staff)):
    items = [await _advertiser_summary(item) for item in await _advertiser_users()]
    query = q.strip().lower()
    if query:
        items = [item for item in items if query in " ".join(str(v) for v in item.values()).lower()]
    if status:
        items = [item for item in items if status.upper() in {str(item["account_status"]).upper(), str(item["identity_status"]).upper()}]
    return _page(items, page, limit)


@router.get("/advertisers/{reference}")
async def advertiser_detail(reference: str, user: dict = Depends(require_staff)):
    advertiser = await _find_advertiser(reference)
    summary = await _advertiser_summary(advertiser)
    profile = _clean(await db.advertiser_profiles.find_one({"user_id": advertiser["id"]}, {"_id": 0}))
    documents = await db.identity_documents.find(
        {"user_id": advertiser["id"]}, {"_id": 0, "storage_path": 0, "url": 0}
    ).sort("created_at", -1).to_list(20)
    submissions = await db.advertiser_submissions.find({"user_id": advertiser["id"]}, {"_id": 0}).sort("submitted_at", -1).to_list(100)
    audit = await db.audit_events.find(
        {"$or": [{"subject_id": advertiser["id"]}, {"subject_id": summary["reference"]}]}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    notes = await db.staff_property_notes.find(
        {"advertiser_id": advertiser["id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return {**summary, "profile": profile, "identity_documents": documents,
            "submissions": await _submission_summaries(submissions), "audit": audit, "internal_notes": notes}


@router.get("/staff-options")
async def staff_options(user: dict = Depends(require_staff)):
    return await db.users.find(
        {"account_category": "STAFF", "status": "ACTIVE"},
        {"_id": 0, "id": 1, "name": 1, "email": 1, "role": 1},
    ).sort("name", 1).to_list(500)


@router.put("/advertisers/{reference}/identity")
async def identity_decision(reference: str, payload: DecisionIn, user: dict = Depends(require_staff)):
    _require_capability(user, "identity")
    advertiser = await _find_advertiser(reference)
    action = payload.action.upper()
    allowed = {"VERIFY", "REJECT", "REQUEST_DOCUMENTS", "REQUEST_RESUBMISSION"}
    if action not in allowed:
        raise HTTPException(400, "Invalid identity action")
    documents = await db.identity_documents.find({"user_id": advertiser["id"]}).to_list(20)
    if action in {"VERIFY", "REJECT"} and not documents:
        raise HTTPException(409, "No identity document has been submitted")
    previous = next((str(item.get("status")) for item in documents), "NOT_STARTED")
    new_status = {"VERIFY": "VERIFIED", "REJECT": "REJECTED",
                  "REQUEST_DOCUMENTS": "DOCUMENTS_REQUESTED",
                  "REQUEST_RESUBMISSION": "RESUBMISSION_REQUESTED"}[action]
    timestamp = now_iso()
    if documents:
        await db.identity_documents.update_many(
            {"user_id": advertiser["id"]},
            {"$set": {"status": new_status, "reviewed_by": user["id"], "reviewed_at": timestamp,
                      "review_reason": payload.reason, "review_notes": payload.notes}},
        )
    await db.advertiser_profiles.update_one(
        {"user_id": advertiser["id"]}, {"$set": {"identity_status": new_status, "updated_at": timestamp}}, upsert=True
    )
    event = await _audit(user, "advertiser_identity", advertiser["id"], action, previous,
                         new_status, payload.reason, payload.notes)
    return {"ok": True, "status": new_status, "audit_event": event}


@router.put("/advertisers/{reference}/contact-verification")
async def contact_verification(reference: str, payload: ContactVerificationIn,
                               user: dict = Depends(require_staff)):
    _require_capability(user, "identity")
    advertiser = await _find_advertiser(reference)
    action = payload.action.upper()
    if action not in {"VERIFY", "RESET"}:
        raise HTTPException(400, "Invalid contact-verification action")
    field = "email_verified" if payload.channel == "EMAIL" else "mobile_verified"
    previous = "VERIFIED" if advertiser.get(field) else "UNVERIFIED"
    if payload.action.upper() == "VERIFY" and advertiser.get(field):
        raise HTTPException(409, f"{payload.channel.title()} is already verified")
    verified = action == "VERIFY"
    await db.users.update_one(
        {"id": advertiser["id"]},
        {"$set": {field: verified, f"{field}_at": now_iso() if verified else None}},
    )
    new_status = "VERIFIED" if verified else "UNVERIFIED"
    event = await _audit(user, "advertiser_contact", advertiser["id"],
                         f"{action}_{payload.channel}", previous, new_status,
                         payload.reason, payload.notes, {"channel": payload.channel})
    return {"ok": True, "channel": payload.channel, "status": new_status, "audit_event": event}


@router.put("/advertisers/{reference}/manage")
async def manage_advertiser(reference: str, payload: AdvertiserManagementIn,
                            user: dict = Depends(require_staff)):
    advertiser = await _find_advertiser(reference)
    action = payload.action.upper()
    if action not in {"ASSIGN", "SUSPEND", "REACTIVATE", "ADD_NOTE"}:
        raise HTTPException(400, "Invalid advertiser-management action")
    if action in {"SUSPEND", "REACTIVATE"}:
        _require_capability(user, "account_management")
    if action in {"ASSIGN", "ADD_NOTE"}:
        _require_capability(user, "submission")
    previous = advertiser.get("status", "ACTIVE")
    metadata = {}
    if action == "ASSIGN":
        if not payload.assigned_staff_id:
            raise HTTPException(400, "Select a Staff member")
        staff = await db.users.find_one(
            {"id": payload.assigned_staff_id, "account_category": "STAFF", "status": "ACTIVE"},
            {"_id": 0, "password_hash": 0},
        )
        if not staff:
            raise HTTPException(404, "Selected Staff account was not found")
        await db.advertiser_profiles.update_one(
            {"user_id": advertiser["id"]},
            {"$set": {"assigned_staff_id": staff["id"],
                      "assigned_staff_name": staff.get("name") or staff.get("email"),
                      "updated_at": now_iso()}}, upsert=True,
        )
        new_status = previous
        metadata = {"assigned_staff_id": staff["id"], "assigned_staff_name": staff.get("name")}
    elif action == "ADD_NOTE":
        note = {"id": new_id(), "advertiser_id": advertiser["id"], "author_id": user["id"],
                "author_name": user.get("name") or user.get("email"), "text": payload.notes or payload.reason,
                "created_at": now_iso()}
        await db.staff_property_notes.insert_one(note)
        new_status = previous
    else:
        new_status = "SUSPENDED" if action == "SUSPEND" else "ACTIVE"
        await db.users.update_one({"id": advertiser["id"]}, {"$set": {"status": new_status, "updated_at": now_iso()}})
    event = await _audit(user, "advertiser_account", advertiser["id"], action,
                         previous, new_status, payload.reason, payload.notes, metadata)
    return {"ok": True, "status": new_status, "audit_event": event}


@router.get("/documents/{document_id}")
async def secure_document(document_id: str, user: dict = Depends(require_staff)):
    """Stream a review document only after Staff authentication."""
    record = await db.identity_documents.find_one({"id": document_id})
    if not record:
        record = await db.files.find_one({"id": document_id, "is_deleted": False})
    if not record or not record.get("storage_path"):
        raise HTTPException(404, "Document not found")
    data, detected_type = _get_object(record["storage_path"])
    filename = str(record.get("original_filename") or record.get("file_name") or "document").replace('"', "")
    return Response(content=data, media_type=record.get("content_type") or detected_type,
                    headers={"Cache-Control": "private, no-store",
                             "Content-Disposition": f'inline; filename="{filename}"'})


@router.get("/submissions")
async def submissions(q: str = "", status: str = "", page: int = Query(1, ge=1),
                      limit: int = Query(25, ge=1, le=100), user: dict = Depends(require_staff)):
    rows = await db.advertiser_submissions.find({}, {"_id": 0}).sort("submitted_at", -1).to_list(5000)
    reviews = await _reviews()
    items = await _submission_summaries(rows, reviews)
    query = q.strip().lower()
    if query:
        items = [item for item in items if query in " ".join(str(v) for k, v in item.items() if k != "data").lower()]
    if status:
        items = [item for item in items if status_token(item["status"]) == status_token(status)]
    return _page(items, page, limit)


@router.get("/submissions/{reference}")
async def submission_detail(reference: str, user: dict = Depends(require_staff)):
    return await _submission_detail(reference)


@router.put("/submissions/{reference}/decision")
async def submission_decision(reference: str, payload: DecisionIn, user: dict = Depends(require_staff)):
    _require_capability(user, "submission")
    row = await _find_submission(reference)
    action = payload.action.upper()
    statuses = {"APPROVE": "APPROVED", "RETURN": "INFORMATION_REQUIRED", "HOLD": "ON_HOLD",
                "REOPEN": "UNDER_REVIEW", "REJECT": "REJECTED"}
    previous = status_token((await _submission_summary(row)).get("status")) or "UNDER_REVIEW"
    allowed = {
        "UNDER_REVIEW": {"APPROVE", "RETURN", "HOLD", "REJECT"},
        "INFORMATION_REQUIRED": {"REOPEN", "HOLD", "REJECT"},
        "ON_HOLD": {"REOPEN", "RETURN", "REJECT"},
        "APPROVED": {"REOPEN"},
        "REJECTED": {"REOPEN"},
    }
    if action not in allowed.get(previous, set()):
        raise HTTPException(409, f"Submission cannot perform {action} while {previous}")
    if action == "APPROVE":
        blockers = content_blockers(row.get("data") or {})
        if blockers:
            raise HTTPException(409, {"message": "Submission is incomplete", "blockers": blockers})
    new_status = statuses[action]
    await db.staff_property_reviews.update_one(
        {"subject_ref": reference},
        {"$set": {"submission_status": new_status, "submission_reason": payload.reason,
                  "submission_notes": payload.notes, "updated_at": now_iso()},
         "$setOnInsert": {"id": new_id(), "subject_ref": reference, "created_at": now_iso()}}, upsert=True,
    )
    await db.advertiser_submissions.update_one({"id": row["id"]}, {"$set": {"status": new_status, "updated_at": now_iso()}})
    event = await _audit(user, "property_submission", reference, action, previous, new_status, payload.reason, payload.notes)
    return {"ok": True, "status": new_status, "audit_event": event}


@router.get("/master-properties")
async def master_property_options(q: str = "", user: dict = Depends(require_staff)):
    query = q.strip()
    mongo_query: dict[str, Any] = {
        "title": {"$type": "string", "$ne": ""},
        "lifecycle_status": {"$ne": "deleted"},
    }
    if query:
        pattern = {"$regex": re.escape(query), "$options": "i"}
        mongo_query["$or"] = [{"title": pattern}, {"id": pattern}]
    rows = await db.master_properties.find(
        mongo_query, {"_id": 0, "id": 1, "title": 1, "lifecycle_status": 1}
    ).sort("updated_at", -1).to_list(50)
    return rows


@router.put("/submissions/{reference}/conflict")
async def conflict_decision(reference: str, payload: ConflictDecisionIn, user: dict = Depends(require_staff)):
    _require_capability(user, "submission")
    await _find_submission(reference)
    action = payload.action.upper()
    statuses = {"REQUEST_CLARIFICATION": "CLARIFICATION_REQUESTED", "CONFIRM_NEW": "NEW_PROPERTY_CONFIRMED", "LINK_MASTER": "LINKED_TO_MASTER", "RECHECK": None}
    if action not in statuses:
        raise HTTPException(400, "Invalid conflict action")
    row = await _find_submission(reference)
    signature = _identity_signature(row.get("data") or {})
    master_property_id = str(payload.master_property_id or "").strip() or None
    if action == "LINK_MASTER":
        if not master_property_id:
            raise HTTPException(400, "Select the Master Property to link")
        if not await db.master_properties.find_one({"id": master_property_id}, {"_id": 0, "id": 1}):
            raise HTTPException(404, "Selected Master Property was not found")
    review = await db.staff_property_reviews.find_one({"subject_ref": reference}) or {}
    previous = review.get("conflict_status", "NOT_CHECKED")
    if action == "RECHECK":
        candidates = await _duplicate_candidates(row)
        new_status = "POSSIBLE" if candidates else "CLEAR"
    else:
        candidates = []
        new_status = statuses[action]
    review_updates = {"conflict_status": new_status, "conflict_reason": payload.reason,
                      "conflict_notes": payload.notes, "updated_at": now_iso(),
                      "conflict_identity_signature": signature,
                      "conflict_resolution_stale": False,
                      "master_property_id": master_property_id if action == "LINK_MASTER" else None}
    await db.staff_property_reviews.update_one(
        {"subject_ref": reference}, {"$set": review_updates,
        "$setOnInsert": {"id": new_id(), "subject_ref": reference, "created_at": now_iso()}}, upsert=True)
    await db.advertiser_submissions.update_one(
        {"$or": [{"reference": reference}, {"id": reference}]},
        {"$set": {"master_property_id": master_property_id, "updated_at": now_iso()}},
    )
    event = await _audit(user, "property_conflict", reference, action, previous, new_status,
                         payload.reason, payload.notes, {"master_property_id": master_property_id})
    return {"ok": True, "status": new_status, "master_property_id": master_property_id,
            "duplicate_candidates": candidates, "audit_event": event}


@router.put("/submissions/{reference}/authority")
async def authority_decision(reference: str, payload: DecisionIn, user: dict = Depends(require_staff)):
    _require_capability(user, "authority")
    await _find_submission(reference)
    action = payload.action.upper()
    statuses = {"ACCEPT": "ACCEPTED", "HOLD": "ON_HOLD", "REQUEST_EVIDENCE": "EVIDENCE_REQUESTED"}
    if action not in statuses:
        raise HTTPException(400, "Invalid authority action")
    review = await db.staff_property_reviews.find_one({"subject_ref": reference}) or {}
    previous = status_token(review.get("authority_status") or "PENDING")
    allowed = {
        "PENDING": {"ACCEPT", "HOLD", "REQUEST_EVIDENCE"},
        "EVIDENCE_REQUESTED": {"ACCEPT", "HOLD", "REQUEST_EVIDENCE"},
        "ON_HOLD": {"ACCEPT", "REQUEST_EVIDENCE"},
        "ACCEPTED": {"HOLD", "REQUEST_EVIDENCE"},
    }
    if action not in allowed.get(previous, set()):
        raise HTTPException(409, f"Authority cannot perform {action} while {previous}")
    if action == "ACCEPT":
        submission = await _find_submission(reference)
        if not (submission.get("data") or {}).get("authority_confirmed"):
            raise HTTPException(409, "The advertiser has not confirmed authority to advertise")
        documents = await db.files.count_documents({
            "uploaded_by": submission.get("user_id"), "source": "property_document", "is_deleted": False,
        })
        if not documents:
            raise HTTPException(409, "Authority evidence has not been submitted")
    new_status = statuses[action]
    await db.staff_property_reviews.update_one(
        {"subject_ref": reference}, {"$set": {"authority_status": new_status,
        "authority_reason": payload.reason, "authority_notes": payload.notes, "updated_at": now_iso()},
        "$setOnInsert": {"id": new_id(), "subject_ref": reference, "created_at": now_iso()}}, upsert=True)
    event = await _audit(user, "property_authority", reference, action, previous, new_status, payload.reason, payload.notes)
    return {"ok": True, "status": new_status, "audit_event": event}


async def _publication_items() -> list[dict]:
    rows = await db.advertiser_submissions.find({}, {"_id": 0}).sort("submitted_at", -1).to_list(5000)
    reviews = await _reviews()
    results = []
    items = await _submission_summaries(rows, reviews)
    for item in items:
        review = reviews.get(item["reference"], {})
        advertiser = await db.users.find_one({"id": item["user_id"]}, {"_id": 0, "password_hash": 0}) or {}
        identity_verified = await db.identity_documents.count_documents({"user_id": item["user_id"], "status": "VERIFIED"}) > 0
        blockers = []
        if item["status"] != "APPROVED": blockers.append("Submission not approved")
        if not identity_verified: blockers.append("Identity not verified")
        if not (advertiser.get("email_verified") or advertiser.get("google_email_verified")):
            blockers.append("Email not verified")
        if not (advertiser.get("mobile_verified") or advertiser.get("phone_verified")):
            blockers.append("Mobile number not verified")
        if item["authority_status"] != "ACCEPTED": blockers.append("Authority not accepted")
        if item["conflict_status"] in {"POSSIBLE", "CLARIFICATION_REQUESTED"}: blockers.append("Property conflict not cleared")
        if item.get("conflict_resolution_stale"):
            blockers.append("Property identity changed; duplicate check must be rerun")
        blockers.extend(content_blockers(item["data"]))
        results.append({**item, "publication_status": review.get("publication_status") or "DRAFT",
                        "identity_status": "VERIFIED" if identity_verified else "PENDING",
                        "email_verified": bool(advertiser.get("email_verified") or advertiser.get("google_email_verified")),
                        "mobile_verified": bool(advertiser.get("mobile_verified") or advertiser.get("phone_verified")),
                        "price_label": price_label(item["data"]),
                        "readiness": "READY" if not blockers else "BLOCKED", "blockers": blockers})
    return results


def _photo_urls(data: dict) -> list[str]:
    return [str(item if isinstance(item, str) else item.get("url") or "").strip()
            for item in data.get("photos") or []
            if str(item if isinstance(item, str) else item.get("url") or "").strip()]


def _integrated_payload(item: dict, advertiser: dict) -> dict:
    data = item.get("data") or {}
    price_type = status_token(data.get("price_type") or data.get("currency") or "PGK")
    amount = float(data.get("price") or 0) if price_type == "PGK" else 0.0
    relationship = status_token(data.get("relationship"))
    authority_basis = {
        "OWNER_JOINT_OWNER": "OWNER",
        "AUTHORISED_REAL_ESTATE_AGENT": "AUTHORISED_AGENT",
        "AUTHORISED_REPRESENTATIVE": "AUTHORISED_REPRESENTATIVE",
    }.get(relationship, "OWNER")
    location = (data.get("city") or data.get("town") or data.get("location")
                or data.get("suburb") or data.get("street"))
    map_coords = None
    if data.get("latitude") not in {None, ""} and data.get("longitude") not in {None, ""}:
        map_coords = f"{data['latitude']},{data['longitude']}"
    return {
        "title": data.get("title"), "description": data.get("description"),
        "listing_type": str(data.get("listing_type") or "").lower(),
        "property_type": data.get("property_type"), "province": data.get("province"),
        "location": location, "suburb": data.get("suburb") or location,
        "street_name": data.get("street"), "address": data.get("address"),
        "nearby_landmark": data.get("landmark"), "map_coords": map_coords,
        "allotment_number": data.get("lot"), "section_number": data.get("section"),
        "full_portion_number": data.get("portion"),
        "area_sqm": optional_number(data.get("building_area") or data.get("land_size")),
        "bedrooms": data.get("bedrooms") or 0, "bathrooms": data.get("bathrooms") or 0,
        "parking": data.get("parking") or 0, "features": data.get("features") or [],
        "images": _photo_urls(data), "price": amount, "currency": "PGK",
        "status": "active", "verified": True, "featured": False,
        "owner_name": advertiser.get("name") or "Property Advertiser",
        "owner_email": advertiser.get("email"), "owner_phone": advertiser.get("phone"),
        "owner_relationship": authority_basis, "authority_status": "VERIFIED",
        "duplicate_override": True,
    }


async def _sync_public_listing(item: dict, user: dict, new_status: str) -> dict:
    listing_reference = item["listing_reference"]
    existing = await db.listings.find_one({"listing_reference": listing_reference}, {"_id": 0})
    timestamp = now_iso()
    if new_status != "PUBLISHED":
        if existing:
            await db.listings.update_one(
                {"id": existing["id"]},
                {"$set": {"publication_status": "withdrawn", "responsible_channel_active": False,
                          "updated_at": timestamp}},
            )
            await db.listing_status_history.insert_one({
                "id": new_id(), "listing_id": existing["id"], "status": "withdrawn",
                "changed_at": timestamp, "changed_by": user["id"],
            })
        return {"property_id": (existing or {}).get("property_id"), "listing_id": (existing or {}).get("id")}
    advertiser = await db.users.find_one({"id": item["user_id"]}, {"_id": 0, "password_hash": 0}) or {}
    data = item.get("data") or {}
    price_type = status_token(data.get("price_type") or data.get("currency") or "PGK")
    amount = float(data.get("price") or 0) if price_type == "PGK" else 0.0
    if existing:
        await db.listings.update_one({"id": existing["id"]}, {"$set": {
            "publication_status": "active", "responsible_channel_active": True,
            "price_current": amount, "price_type": price_type, "price_label": price_label(data),
            "service": data.get("service"), "title": data.get("title"),
            "description": data.get("description") or "", "updated_at": timestamp,
        }})
        await db.listing_status_history.insert_one({
            "id": new_id(), "listing_id": existing["id"], "status": "active",
            "changed_at": timestamp, "changed_by": user["id"],
        })
        return {"property_id": existing["property_id"], "listing_id": existing["id"]}
    property_id = item.get("master_property_id")
    if property_id:
        if not await db.master_properties.find_one({"id": property_id}, {"_id": 0, "id": 1}):
            raise HTTPException(409, "Linked Master Property no longer exists")
        listing_id = new_id()
        transaction = str(data.get("listing_type") or "").upper()
        listing = {
            "id": listing_id, "property_id": property_id, "transaction_type": transaction,
            "publication_status": "active", "responsible_channel_active": True,
            "price_current": amount, "currency": "PGK", "price_type": price_type,
            "price_label": price_label(data), "title": data.get("title"),
            "description": data.get("description") or "", "featured": False,
            "listing_reference": listing_reference, "service": data.get("service"),
            "created_at": timestamp, "updated_at": timestamp,
        }
        await db.listings.insert_one(listing)
        await db.listing_prices.insert_one({
            "id": new_id(), "listing_id": listing_id, "amount": amount, "currency": "PGK",
            "basis": "TOTAL_SALE" if transaction == "SALE" else "MONTHLY_RENT",
            "effective_from": timestamp, "created_at": timestamp,
        })
        media = [{"id": new_id(), "listing_id": listing_id, "url": url, "sort_order": index,
                  "is_cover": index == 0, "created_at": timestamp}
                 for index, url in enumerate(_photo_urls(data))]
        if media:
            await db.listing_media.insert_many(media)
        await db.listing_status_history.insert_one({
            "id": new_id(), "listing_id": listing_id, "status": "active",
            "changed_at": timestamp, "changed_by": user["id"],
        })
    else:
        service = IntegratedPropertyService(db, client)
        created = await service.create(_integrated_payload(item, advertiser), advertiser)
        property_id, listing_id = created["integrated_property_id"], created["integrated_listing_id"]
        await db.listings.update_one({"id": listing_id}, {"$set": {
            "listing_reference": listing_reference, "service": data.get("service"),
            "price_type": price_type, "price_label": price_label(data),
        }})
    await db.staff_property_reviews.update_one(
        {"subject_ref": item["reference"]},
        {"$set": {"master_property_id": property_id, "integrated_listing_id": listing_id,
                  "updated_at": timestamp}},
    )
    await db.advertiser_submissions.update_one(
        {"id": item["id"]}, {"$set": {"master_property_id": property_id,
                                        "integrated_listing_id": listing_id, "updated_at": timestamp}},
    )
    return {"property_id": property_id, "listing_id": listing_id}


@router.get("/publications")
async def publications(q: str = "", status: str = "", page: int = Query(1, ge=1),
                       limit: int = Query(25, ge=1, le=100), user: dict = Depends(require_staff)):
    items = await _publication_items()
    query = q.strip().lower()
    if query: items = [item for item in items if query in " ".join(str(v) for k, v in item.items() if k not in {"data", "blockers"}).lower()]
    if status: items = [item for item in items if status_token(item["publication_status"]) == status_token(status)]
    return _page(items, page, limit)


@router.get("/publications/{listing_reference}")
async def publication_detail(listing_reference: str, user: dict = Depends(require_staff)):
    for item in await _publication_items():
        if item["listing_reference"] == listing_reference:
            detail = await _submission_detail(item["reference"])
            return {**item, "documents": detail["documents"], "audit": detail["audit"]}
    raise HTTPException(404, "Listing not found")


@router.put("/publications/{listing_reference}/decision")
async def publication_decision(listing_reference: str, payload: DecisionIn, user: dict = Depends(require_staff)):
    _require_capability(user, "publication")
    item = next((row for row in await _publication_items() if row["listing_reference"] == listing_reference), None)
    if not item: raise HTTPException(404, "Listing not found")
    action = payload.action.upper()
    previous = item["publication_status"]
    new_status = publication_transition(previous, action)
    if not new_status:
        raise HTTPException(409, f"Publication cannot perform {action} while {status_token(previous) or 'DRAFT'}")
    if action == "PUBLISH" and item["blockers"]:
        raise HTTPException(409, {"message": "Publication requirements are incomplete", "blockers": item["blockers"]})
    try:
        integrated = await _sync_public_listing(item, user, new_status)
    except DuplicatePropertyError as exc:
        raise HTTPException(
            409,
            {"message": "A matching Master Property must be resolved before publication",
             "candidates": exc.candidates},
        ) from exc
    except ValueError as exc:
        # Reference failures (province, town, suburb or property type) are
        # actionable publication blockers, not opaque server errors.
        raise HTTPException(409, f"Publication data could not be linked: {exc}") from exc
    except PartialWriteError as exc:
        raise HTTPException(
            500,
            f"Publication storage failed safely; reference {exc.failure_id}",
        ) from exc
    timestamp = now_iso()
    if new_status == "PUBLISHED":
        deadlines = lifecycle_deadlines(timestamp)
        await db.advertiser_listing_lifecycle.update_one(
            {"listing_id": listing_reference},
            {"$set": {"user_id": item["user_id"], "status": "AVAILABLE",
                      "workflow_status": "CURRENT", "updated_at": timestamp, **deadlines},
             "$unset": {"next_reminder_due": "", "suspended_at": "", "archived_at": ""},
             "$setOnInsert": {"id": new_id(), "listing_id": listing_reference,
                              "created_at": timestamp, "published_at": timestamp}},
            upsert=True,
        )
    elif new_status in {"SUSPENDED", "UNPUBLISHED"}:
        await db.advertiser_listing_lifecycle.update_one(
            {"listing_id": listing_reference},
            {"$set": {"user_id": item["user_id"], "workflow_status": "SUSPENDED",
                      "suspended_at": timestamp, "updated_at": timestamp},
             "$setOnInsert": {"id": new_id(), "listing_id": listing_reference,
                              "created_at": timestamp}},
            upsert=True,
        )
    await db.staff_property_reviews.update_one(
        {"subject_ref": item["reference"]}, {"$set": {"publication_status": new_status,
        "publication_reason": payload.reason, "publication_notes": payload.notes,
        "listing_reference": listing_reference, "updated_at": timestamp},
        "$setOnInsert": {"id": new_id(), "subject_ref": item["reference"], "created_at": timestamp}}, upsert=True)
    event = await _audit(user, "property_listing", listing_reference, action, previous, new_status, payload.reason, payload.notes,
                         {"submission_reference": item["reference"], **integrated})
    return {"ok": True, "status": new_status, "integrated": integrated, "audit_event": event}


async def run_lifecycle_maintenance(now: Optional[datetime] = None) -> dict[str, int]:
    """Advance due confirmations, reminders, unpublishing and archiving."""
    current = now or datetime.now(timezone.utc)
    publications = {item["listing_reference"]: item for item in await _publication_items()}
    rows = await db.advertiser_listing_lifecycle.find({}, {"_id": 0}).to_list(5000)
    counts = {"confirmations": 0, "reminders": 0, "unpublished": 0, "archived": 0}
    system_user = {"id": "system", "name": "Lifecycle Scheduler", "role": "system_admin"}
    for row in rows:
        listing_reference = row.get("listing_id")
        item = publications.get(listing_reference)
        if not listing_reference or not item:
            continue
        workflow = status_token(row.get("workflow_status") or "CURRENT")
        availability = status_token(row.get("status") or "AVAILABLE")
        if availability in {"SOLD", "LEASED", "WITHDRAWN"}:
            continue
        archive_due = parse_datetime(row.get("archive_due"))
        unpublish_due = parse_datetime(row.get("unpublish_due"))
        next_due = parse_datetime(row.get("next_due"))
        reminder_until = parse_datetime(row.get("reminder_until"))
        next_reminder = parse_datetime(row.get("next_reminder_due"))
        timestamp = current.isoformat()
        if archive_due and current >= archive_due and workflow != "ARCHIVED":
            await db.advertiser_listing_lifecycle.update_one(
                {"id": row["id"]}, {"$set": {"workflow_status": "ARCHIVED",
                "archived_at": timestamp, "updated_at": timestamp}},
            )
            await db.staff_property_reviews.update_one(
                {"subject_ref": item["reference"]},
                {"$set": {"publication_status": "UNPUBLISHED", "updated_at": timestamp}},
            )
            await _sync_public_listing(item, system_user, "UNPUBLISHED")
            await _audit(system_user, "property_listing", listing_reference,
                         "AUTO_ARCHIVE", workflow, "ARCHIVED",
                         "Twelve months elapsed since availability confirmation")
            counts["archived"] += 1
            continue
        if unpublish_due and current >= unpublish_due and workflow not in {"SUSPENDED", "ARCHIVED"}:
            await db.advertiser_listing_lifecycle.update_one(
                {"id": row["id"]}, {"$set": {"workflow_status": "SUSPENDED",
                "suspended_at": timestamp, "updated_at": timestamp}},
            )
            await db.staff_property_reviews.update_one(
                {"subject_ref": item["reference"]},
                {"$set": {"publication_status": "UNPUBLISHED", "updated_at": timestamp}},
            )
            await _sync_public_listing(item, system_user, "UNPUBLISHED")
            await _audit(system_user, "property_listing", listing_reference,
                         "AUTO_UNPUBLISH", workflow, "SUSPENDED",
                         "Six months elapsed without availability confirmation")
            counts["unpublished"] += 1
            continue
        advertiser = await db.users.find_one(
            {"id": item.get("user_id")}, {"_id": 0, "email": 1, "name": 1}
        ) or {}
        if next_due and current >= next_due and workflow == "CURRENT":
            next_reminder_due = add_months(current, 1).isoformat()
            await db.advertiser_listing_lifecycle.update_one(
                {"id": row["id"]}, {"$set": {"workflow_status": "AWAITING_ADVERTISER",
                "confirmation_requested_at": timestamp, "next_reminder_due": next_reminder_due,
                "reminder_count": 0, "updated_at": timestamp}},
            )
            await notify("Confirm that your property is still available",
                         f"Please review and confirm listing {listing_reference}.", advertiser.get("email"))
            await _audit(system_user, "property_listing", listing_reference,
                         "AUTO_SEND_CONFIRMATION", workflow, "AWAITING_ADVERTISER",
                         "Quarterly availability confirmation became due")
            counts["confirmations"] += 1
        elif (workflow == "AWAITING_ADVERTISER" and next_reminder and current >= next_reminder
              and reminder_until and current <= reminder_until):
            next_reminder_due = add_months(current, 1).isoformat()
            await db.advertiser_listing_lifecycle.update_one(
                {"id": row["id"]}, {"$set": {"next_reminder_due": next_reminder_due,
                "last_reminder_at": timestamp, "updated_at": timestamp}, "$inc": {"reminder_count": 1}},
            )
            await notify("Property availability confirmation reminder",
                         f"Listing {listing_reference} is awaiting your confirmation.", advertiser.get("email"))
            await _audit(system_user, "property_listing", listing_reference,
                         "AUTO_CONFIRMATION_REMINDER", workflow, workflow,
                         "Monthly reminder during the two-month confirmation period")
            counts["reminders"] += 1
    return counts


async def lifecycle_maintenance_loop() -> None:
    while True:
        await asyncio.sleep(3600)
        try:
            await run_lifecycle_maintenance()
        except Exception:
            # The next hourly pass retries; request handling must remain available.
            continue


async def _lifecycle_items() -> list[dict]:
    publications = await _publication_items()
    items = []
    for pub in publications:
        if pub["publication_status"] not in {"PUBLISHED", "SUSPENDED", "UNPUBLISHED"}: continue
        stored = await db.advertiser_listing_lifecycle.find_one({"listing_id": pub["listing_reference"]}, {"_id": 0}) or {}
        items.append({**pub, "availability": stored.get("status") or "AVAILABLE",
                      "last_confirmed": stored.get("last_confirmed"), "next_due": stored.get("next_due"),
                      "unpublish_due": stored.get("unpublish_due"), "archive_due": stored.get("archive_due"),
                      "reminder_count": stored.get("reminder_count") or 0,
                      "lifecycle_status": stored.get("workflow_status") or "CURRENT"})
    return items


@router.get("/lifecycle")
async def lifecycle(q: str = "", status: str = "", page: int = Query(1, ge=1),
                    limit: int = Query(25, ge=1, le=100), user: dict = Depends(require_staff)):
    items = await _lifecycle_items()
    counts = {token: sum(1 for item in items if lifecycle_filter_match(item, token))
              for token in ("CURRENT", "SOLD", "LEASED", "WITHDRAWN", "SUSPENDED", "ARCHIVED")}
    query = q.strip().lower()
    if query: items = [item for item in items if query in " ".join(str(v) for k, v in item.items() if k not in {"data", "blockers"}).lower()]
    if status:
        selected = status_token(status)
        items = [item for item in items if lifecycle_filter_match(item, selected)]
    result = _page(items, page, limit)
    result["counts"] = counts
    return result


@router.get("/lifecycle/{listing_reference}")
async def lifecycle_detail(listing_reference: str, user: dict = Depends(require_staff)):
    item = next((row for row in await _lifecycle_items() if row["listing_reference"] == listing_reference), None)
    if not item: raise HTTPException(404, "Lifecycle record not found")
    item["audit"] = await db.audit_events.find({"subject_id": listing_reference}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return item


@router.put("/lifecycle/{listing_reference}/decision")
async def lifecycle_decision(listing_reference: str, payload: LifecycleDecisionIn, user: dict = Depends(require_staff)):
    _require_capability(user, "lifecycle")
    item = next((row for row in await _lifecycle_items() if row["listing_reference"] == listing_reference), None)
    if not item: raise HTTPException(404, "Lifecycle record not found")
    action = payload.action.upper()
    previous = status_token(item.get("lifecycle_status")) or "CURRENT"
    if not lifecycle_action_allowed(previous, action, item.get("availability"),
                                    item.get("publication_status")):
        raise HTTPException(409, f"Lifecycle cannot perform {action} for this listing state")
    new_status = lifecycle_transition(previous, action)
    if not new_status:
        raise HTTPException(409, f"Lifecycle cannot perform {action} while {previous}")
    if action == "RECORD_RESPONSE" and not payload.availability:
        raise HTTPException(400, "Availability is required when recording a response")
    if action == "RECORD_RESPONSE" and any(value is None for value in (
        payload.price_confirmed, payload.description_confirmed, payload.photos_confirmed,
        payload.contact_confirmed, payload.inspection_confirmed,
    )):
        raise HTTPException(400, "Complete every listing confirmation field")
    if action == "REACTIVATE" and item.get("blockers"):
        raise HTTPException(409, {"message": "Listing requirements must be valid before reactivation",
                                  "blockers": item["blockers"]})
    timestamp = now_iso()
    updates = {"workflow_status": new_status, "updated_at": timestamp, "reason": payload.reason,
               "notes": payload.notes, "user_id": item["user_id"]}
    if payload.availability: updates["status"] = payload.availability
    if action == "REACTIVATE":
        updates["status"] = "AVAILABLE"
        updates.update(lifecycle_deadlines(timestamp))
        updates["reactivated_at"] = timestamp
        updates["reminder_count"] = 0
    if action == "SEND_CONFIRMATION":
        updates["confirmation_requested_at"] = timestamp
        updates["next_reminder_due"] = add_months(parse_datetime(timestamp), 1).isoformat()
        updates["reminder_count"] = 0
    if action == "ARCHIVE":
        updates["archived_at"] = timestamp
    if action == "RECORD_RESPONSE":
        updates.update({"last_confirmed": timestamp, "confirmation": {
            "price": payload.price_confirmed, "description": payload.description_confirmed,
            "photos": payload.photos_confirmed, "contact": payload.contact_confirmed,
            "inspection": payload.inspection_confirmed}})
        if payload.availability in {"AVAILABLE", "UNDER_OFFER"}:
            updates.update(lifecycle_deadlines(timestamp))
            updates["reminder_count"] = 0
    lifecycle_update = {"$set": updates,
        "$setOnInsert": {"id": new_id(), "listing_id": listing_reference, "created_at": timestamp}}
    if action in {"RECORD_RESPONSE", "REACTIVATE"}:
        lifecycle_update["$unset"] = {"next_reminder_due": ""}
    if action == "RECORD_RESPONSE" and payload.availability in {"SOLD", "LEASED", "WITHDRAWN"}:
        lifecycle_update["$unset"] = {
            "next_due": "", "unpublish_due": "", "archive_due": "",
            "next_reminder_due": "", "confirmation_requested_at": "",
        }
    if action == "ARCHIVE":
        lifecycle_update["$unset"] = {
            "next_due": "", "unpublish_due": "", "archive_due": "",
            "next_reminder_due": "", "confirmation_requested_at": "",
        }
    await db.advertiser_listing_lifecycle.update_one(
        {"listing_id": listing_reference}, lifecycle_update, upsert=True)
    unavailable = action == "RECORD_RESPONSE" and payload.availability in {"SOLD", "LEASED", "WITHDRAWN"}
    if action in {"SUSPEND", "ARCHIVE", "REACTIVATE"} or unavailable:
        publication_status = "PUBLISHED" if action == "REACTIVATE" else "SUSPENDED" if action == "SUSPEND" else "UNPUBLISHED"
        await db.staff_property_reviews.update_one({"subject_ref": item["reference"]}, {"$set": {"publication_status": publication_status, "updated_at": timestamp}})
        await _sync_public_listing(item, user, publication_status)
    event = await _audit(user, "property_listing", listing_reference, action, previous, new_status,
                         payload.reason, payload.notes, {"availability": payload.availability})
    return {"ok": True, "status": new_status, "audit_event": event}
