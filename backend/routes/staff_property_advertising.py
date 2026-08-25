"""Staff operations for Property Advertiser accounts and listing workflows.

The advertiser workspace owns draft/submission creation.  This router exposes
the same records to active staff and stores review decisions, publication
state, exact-location consent and immutable audit events.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import secrets
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field

from core.account_policy import require_staff
from core.db import db, new_id, now_iso
from routes.files import _get_object


router = APIRouter(prefix="/property-advertising/staff")

FULL_CONTROL = {"system_admin", "managing_director"}
CAPABILITY_ROLES = {
    "identity": FULL_CONTROL,
    "submission": FULL_CONTROL | {"sales_manager", "sales_agent", "leasing_agent", "property_manager"},
    "authority": FULL_CONTROL | {"sales_manager", "property_manager"},
    "publication": FULL_CONTROL | {"sales_manager", "marketing_officer"},
    "location": FULL_CONTROL | {"sales_manager", "sales_agent", "leasing_agent", "property_manager"},
    "lifecycle": FULL_CONTROL | {"sales_manager", "sales_agent", "leasing_agent", "property_manager", "marketing_officer"},
}


async def ensure_indexes() -> None:
    await db.staff_property_reviews.create_index("subject_ref", unique=True)
    await db.exact_location_requests.create_index("reference", sparse=True)
    await db.exact_location_requests.create_index("access_token_hash", unique=True, sparse=True)
    await db.advertiser_submissions.create_index("reference", sparse=True)


class DecisionIn(BaseModel):
    action: str = Field(min_length=2, max_length=60)
    reason: str = Field(min_length=3, max_length=1000)
    notes: Optional[str] = Field(default=None, max_length=2000)


class LocationDecisionIn(DecisionIn):
    expiry_at: Optional[str] = None
    maximum_views: Optional[int] = Field(default=None, ge=1, le=100)
    consent_confirmed: bool = False


class LifecycleDecisionIn(DecisionIn):
    availability: Optional[Literal["AVAILABLE", "UNDER_OFFER", "SOLD", "LEASED", "WITHDRAWN"]] = None
    price_confirmed: Optional[bool] = None
    description_confirmed: Optional[bool] = None
    photos_confirmed: Optional[bool] = None
    contact_confirmed: Optional[bool] = None
    inspection_confirmed: Optional[bool] = None


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


def _require_capability(user: dict, capability: str) -> None:
    if str(user.get("role") or "") not in CAPABILITY_ROLES[capability]:
        raise HTTPException(403, f"Your Staff role cannot perform {capability} decisions")


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
        "account_status": user.get("status", "ACTIVE"), "role": user.get("role"),
        "relationship": profile.get("relationship_type") or "NOT_SET",
        "profile_status": profile.get("status") or "INCOMPLETE",
        "identity_status": identity_status, "property_count": submission_count,
        "last_active": user.get("last_login_at") or user.get("updated_at") or user.get("created_at"),
        "assigned_staff": profile.get("assigned_staff_name") or "Unassigned",
    }


async def _submission_summary(row: dict, reviews: Optional[dict[str, dict]] = None) -> dict:
    reviews = reviews or await _reviews()
    reference = row.get("reference") or row.get("id")
    data = row.get("data") or {}
    review = reviews.get(reference, {})
    advertiser = await db.users.find_one({"id": row.get("user_id")}, {"_id": 0, "password_hash": 0}) or {}
    profile = await db.advertiser_profiles.find_one({"user_id": row.get("user_id")}, {"_id": 0}) or {}
    conflict_status = review.get("conflict_status")
    if not conflict_status:
        section, lot, suburb = (str(data.get(key) or "").strip().lower() for key in ("section", "lot", "suburb"))
        conflict_status = "CLEAR"
        if section and lot and suburb:
            candidates = await db.advertiser_submissions.find({"id": {"$ne": row.get("id")}}).to_list(5000)
            if any(str((candidate.get("data") or {}).get("section") or "").strip().lower() == section
                   and str((candidate.get("data") or {}).get("lot") or "").strip().lower() == lot
                   and str((candidate.get("data") or {}).get("suburb") or "").strip().lower() == suburb
                   for candidate in candidates):
                conflict_status = "POSSIBLE"
    return {
        "reference": reference, "id": row.get("id"), "user_id": row.get("user_id"),
        "property_title": data.get("title") or "Untitled property",
        "advertiser_name": advertiser.get("name") or "Unknown advertiser",
        "advertiser_reference": _advertiser_reference(advertiser) if advertiser else None,
        "relationship": data.get("relationship") or profile.get("relationship_type") or "NOT_SET",
        "service": data.get("service") or "NOT_SET", "submitted_at": row.get("submitted_at"),
        "review_due": review.get("review_due"), "sla": review.get("sla") or "NOT_CALCULATED",
        "conflict_status": conflict_status,
        "authority_status": review.get("authority_status") or "PENDING",
        "assigned_staff": review.get("assigned_staff_name") or "Unassigned",
        "status": review.get("submission_status") or row.get("status") or "UNDER_REVIEW",
        "listing_reference": _listing_reference(row, review), "data": data,
    }


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
    reviews = await _reviews()
    publication_ready = sum(1 for row in reviews.values() if row.get("publication_status") == "READY")
    location_pending = await db.exact_location_requests.count_documents({"status": {"$in": ["PENDING", "AWAITING_ADVERTISER"]}})
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
            priorities.append({"id": submission.get("id"), "priority": "NORMAL", "task": "Submission review",
                "subject_label": (submission.get("data") or {}).get("title") or submission.get("reference"),
                "assigned_staff_name": "Unassigned", "due_at": submission.get("submitted_at"),
                "path": f"/admin/property-advertising/submissions/{submission.get('reference')}"})
    return {
        "stats": {"advertisers": len(advertisers), "submissions": submissions,
                  "pending_identity": pending_identity, "ready_to_publish": publication_ready,
                  "location_pending": location_pending},
        "priorities": priorities,
    }


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
    return {**summary, "profile": profile, "identity_documents": documents,
            "submissions": [await _submission_summary(item) for item in submissions], "audit": audit}


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
    items = [await _submission_summary(row, reviews) for row in rows]
    query = q.strip().lower()
    if query:
        items = [item for item in items if query in " ".join(str(v) for k, v in item.items() if k != "data").lower()]
    if status:
        items = [item for item in items if str(item["status"]).upper() == status.upper()]
    return _page(items, page, limit)


@router.get("/submissions/{reference}")
async def submission_detail(reference: str, user: dict = Depends(require_staff)):
    return await _submission_detail(reference)


@router.put("/submissions/{reference}/decision")
async def submission_decision(reference: str, payload: DecisionIn, user: dict = Depends(require_staff)):
    _require_capability(user, "submission")
    row = await _find_submission(reference)
    action = payload.action.upper()
    statuses = {"APPROVE": "APPROVED", "RETURN": "INFORMATION_REQUIRED", "HOLD": "ON_HOLD", "REOPEN": "UNDER_REVIEW"}
    if action not in statuses:
        raise HTTPException(400, "Invalid submission action")
    previous = (await _submission_summary(row)).get("status")
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


@router.put("/submissions/{reference}/conflict")
async def conflict_decision(reference: str, payload: DecisionIn, user: dict = Depends(require_staff)):
    _require_capability(user, "submission")
    await _find_submission(reference)
    action = payload.action.upper()
    statuses = {"REQUEST_CLARIFICATION": "CLARIFICATION_REQUESTED", "CONFIRM_NEW": "NEW_PROPERTY_CONFIRMED", "LINK_MASTER": "LINKED_TO_MASTER"}
    if action not in statuses:
        raise HTTPException(400, "Invalid conflict action")
    review = await db.staff_property_reviews.find_one({"subject_ref": reference}) or {}
    previous = review.get("conflict_status", "NOT_CHECKED")
    new_status = statuses[action]
    await db.staff_property_reviews.update_one(
        {"subject_ref": reference}, {"$set": {"conflict_status": new_status,
        "conflict_reason": payload.reason, "conflict_notes": payload.notes, "updated_at": now_iso()},
        "$setOnInsert": {"id": new_id(), "subject_ref": reference, "created_at": now_iso()}}, upsert=True)
    event = await _audit(user, "property_conflict", reference, action, previous, new_status, payload.reason, payload.notes)
    return {"ok": True, "status": new_status, "audit_event": event}


@router.put("/submissions/{reference}/authority")
async def authority_decision(reference: str, payload: DecisionIn, user: dict = Depends(require_staff)):
    _require_capability(user, "authority")
    await _find_submission(reference)
    action = payload.action.upper()
    statuses = {"ACCEPT": "ACCEPTED", "HOLD": "ON_HOLD", "REQUEST_EVIDENCE": "EVIDENCE_REQUESTED"}
    if action not in statuses:
        raise HTTPException(400, "Invalid authority action")
    if action == "ACCEPT":
        submission = await _find_submission(reference)
        if not (submission.get("data") or {}).get("authority_confirmed"):
            raise HTTPException(409, "The advertiser has not confirmed authority to advertise")
    review = await db.staff_property_reviews.find_one({"subject_ref": reference}) or {}
    previous = review.get("authority_status", "PENDING")
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
    for row in rows:
        item = await _submission_summary(row, reviews)
        review = reviews.get(item["reference"], {})
        identity_verified = await db.identity_documents.count_documents({"user_id": item["user_id"], "status": "VERIFIED"}) > 0
        blockers = []
        if item["status"] != "APPROVED": blockers.append("Submission not approved")
        if not identity_verified: blockers.append("Identity not verified")
        if item["authority_status"] != "ACCEPTED": blockers.append("Authority not accepted")
        if item["conflict_status"] in {"POSSIBLE", "CLARIFICATION_REQUESTED"}: blockers.append("Property conflict not cleared")
        results.append({**item, "publication_status": review.get("publication_status") or "DRAFT",
                        "identity_status": "VERIFIED" if identity_verified else "PENDING",
                        "readiness": "READY" if not blockers else "BLOCKED", "blockers": blockers})
    return results


@router.get("/publications")
async def publications(q: str = "", status: str = "", page: int = Query(1, ge=1),
                       limit: int = Query(25, ge=1, le=100), user: dict = Depends(require_staff)):
    items = await _publication_items()
    query = q.strip().lower()
    if query: items = [item for item in items if query in " ".join(str(v) for k, v in item.items() if k not in {"data", "blockers"}).lower()]
    if status: items = [item for item in items if item["publication_status"] == status.upper()]
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
    statuses = {"PUBLISH": "PUBLISHED", "RETURN": "CHANGES_REQUIRED", "SUSPEND": "SUSPENDED", "UNPUBLISH": "UNPUBLISHED"}
    if action not in statuses: raise HTTPException(400, "Invalid publication action")
    if action == "PUBLISH" and item["blockers"]:
        raise HTTPException(409, {"message": "Publication requirements are incomplete", "blockers": item["blockers"]})
    previous = item["publication_status"]
    new_status = statuses[action]
    await db.staff_property_reviews.update_one(
        {"subject_ref": item["reference"]}, {"$set": {"publication_status": new_status,
        "publication_reason": payload.reason, "publication_notes": payload.notes,
        "listing_reference": listing_reference, "updated_at": now_iso()},
        "$setOnInsert": {"id": new_id(), "subject_ref": item["reference"], "created_at": now_iso()}}, upsert=True)
    event = await _audit(user, "property_listing", listing_reference, action, previous, new_status, payload.reason, payload.notes,
                         {"submission_reference": item["reference"]})
    return {"ok": True, "status": new_status, "audit_event": event}


@router.get("/exact-location")
async def exact_locations(q: str = "", status: str = "", page: int = Query(1, ge=1),
                          limit: int = Query(25, ge=1, le=100), user: dict = Depends(require_staff)):
    items = await db.exact_location_requests.find({}, {"_id": 0, "exact_location": 0}).sort("created_at", -1).to_list(5000)
    query = q.strip().lower()
    if query: items = [item for item in items if query in " ".join(str(v) for v in item.values()).lower()]
    if status: items = [item for item in items if str(item.get("status", "")).upper() == status.upper()]
    return _page(items, page, limit)


@router.get("/exact-location/{reference}")
async def exact_location_detail(reference: str, user: dict = Depends(require_staff)):
    item = await db.exact_location_requests.find_one({"$or": [{"reference": reference}, {"id": reference}]}, {"_id": 0})
    if not item: raise HTTPException(404, "Exact-location request not found")
    safe = {k: v for k, v in item.items() if k != "exact_location"}
    safe["audit"] = await db.audit_events.find({"subject_id": reference}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return safe


@router.put("/exact-location/{reference}/decision")
async def exact_location_decision(reference: str, payload: LocationDecisionIn, user: dict = Depends(require_staff)):
    _require_capability(user, "location")
    item = await db.exact_location_requests.find_one({"$or": [{"reference": reference}, {"id": reference}]}, {"_id": 0})
    if not item: raise HTTPException(404, "Exact-location request not found")
    action = payload.action.upper()
    statuses = {"SEND_TO_ADVERTISER": "AWAITING_ADVERTISER", "REQUEST_INFORMATION": "INFORMATION_REQUESTED",
                "ARRANGE_INSPECTION": "INSPECTION_OFFERED", "DECLINE": "DECLINED", "SHARE": "ACTIVE"}
    if action not in statuses: raise HTTPException(400, "Invalid location action")
    if action == "SHARE":
        if not payload.consent_confirmed: raise HTTPException(409, "Advertiser consent must be confirmed")
        if not payload.expiry_at: raise HTTPException(409, "Secure access expiry is required")
        try:
            expiry = datetime.fromisoformat(payload.expiry_at.replace("Z", "+00:00"))
            if expiry <= datetime.now(timezone.utc): raise ValueError
        except ValueError:
            raise HTTPException(400, "Expiry must be a future date and time")
    previous = item.get("status", "PENDING")
    new_status = statuses[action]
    token = secrets.token_urlsafe(32) if action == "SHARE" else None
    updates = {"status": new_status, "decision_reason": payload.reason, "decision_notes": payload.notes,
               "reviewed_by": user["id"], "reviewed_at": now_iso()}
    if action == "SHARE": updates.update({"access_token_hash": hashlib.sha256(token.encode()).hexdigest(), "expiry_at": payload.expiry_at,
                                           "maximum_views": payload.maximum_views, "views": 0,
                                           "consent_confirmed": True})
    await db.exact_location_requests.update_one({"id": item["id"]}, {"$set": updates})
    event = await _audit(user, "exact_location_request", reference, action, previous, new_status,
                         payload.reason, payload.notes, {"expiry_at": payload.expiry_at, "maximum_views": payload.maximum_views})
    return {"ok": True, "status": new_status, "secure_access_created": action == "SHARE",
            "secure_path": f"/api/property-advertising/staff/location-access/{token}" if token else None,
            "audit_event": event}


@router.get("/location-access/{token}")
async def use_secure_location_access(token: str):
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    item = await db.exact_location_requests.find_one({"access_token_hash": token_hash, "status": "ACTIVE"})
    if not item:
        raise HTTPException(404, "Secure location access is invalid")
    expiry = datetime.fromisoformat(str(item.get("expiry_at", "")).replace("Z", "+00:00"))
    if expiry <= datetime.now(timezone.utc):
        await db.exact_location_requests.update_one({"id": item["id"]}, {"$set": {"status": "EXPIRED"}})
        raise HTTPException(410, "Secure location access has expired")
    current_views = int(item.get("views") or 0)
    maximum = item.get("maximum_views")
    if maximum and current_views >= int(maximum):
        raise HTTPException(410, "Secure location view limit has been reached")
    result = await db.exact_location_requests.update_one(
        {"id": item["id"], "views": current_views},
        {"$set": {"last_accessed_at": now_iso()}, "$inc": {"views": 1}},
    )
    if not result.modified_count:
        raise HTTPException(409, "Please retry secure location access")
    await db.audit_events.insert_one({"id": new_id(), "action": "EXACT_LOCATION_ACCESSED",
        "subject_type": "exact_location_request", "subject_id": item.get("reference") or item["id"],
        "actor_id": "secure_link_recipient", "created_at": now_iso()})
    return {"property_title": item.get("property_title"), "exact_location": item.get("exact_location"),
            "expires_at": item.get("expiry_at"), "remaining_views": None if not maximum else int(maximum)-current_views-1}


async def _lifecycle_items() -> list[dict]:
    publications = await _publication_items()
    items = []
    for pub in publications:
        if pub["publication_status"] not in {"PUBLISHED", "SUSPENDED", "UNPUBLISHED"}: continue
        stored = await db.advertiser_listing_lifecycle.find_one({"listing_id": pub["listing_reference"]}, {"_id": 0}) or {}
        items.append({**pub, "availability": stored.get("status") or "AVAILABLE",
                      "last_confirmed": stored.get("last_confirmed"), "next_due": stored.get("next_due"),
                      "lifecycle_status": stored.get("workflow_status") or "CURRENT"})
    return items


@router.get("/lifecycle")
async def lifecycle(q: str = "", status: str = "", page: int = Query(1, ge=1),
                    limit: int = Query(25, ge=1, le=100), user: dict = Depends(require_staff)):
    items = await _lifecycle_items()
    query = q.strip().lower()
    if query: items = [item for item in items if query in " ".join(str(v) for k, v in item.items() if k not in {"data", "blockers"}).lower()]
    if status: items = [item for item in items if item["lifecycle_status"] == status.upper()]
    return _page(items, page, limit)


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
    statuses = {"SEND_CONFIRMATION": "AWAITING_ADVERTISER", "RECORD_RESPONSE": "CURRENT",
                "SUSPEND": "SUSPENDED", "ARCHIVE": "ARCHIVED"}
    if action not in statuses: raise HTTPException(400, "Invalid lifecycle action")
    if action == "RECORD_RESPONSE" and not payload.availability:
        raise HTTPException(400, "Availability is required when recording a response")
    previous = item.get("lifecycle_status", "CURRENT")
    new_status = statuses[action]
    timestamp = now_iso()
    updates = {"workflow_status": new_status, "updated_at": timestamp, "reason": payload.reason,
               "notes": payload.notes, "user_id": item["user_id"]}
    if payload.availability: updates["status"] = payload.availability
    if action == "RECORD_RESPONSE":
        updates.update({"last_confirmed": timestamp, "confirmation": {
            "price": payload.price_confirmed, "description": payload.description_confirmed,
            "photos": payload.photos_confirmed, "contact": payload.contact_confirmed,
            "inspection": payload.inspection_confirmed}})
    await db.advertiser_listing_lifecycle.update_one(
        {"listing_id": listing_reference}, {"$set": updates,
        "$setOnInsert": {"id": new_id(), "listing_id": listing_reference, "created_at": timestamp}}, upsert=True)
    if action in {"SUSPEND", "ARCHIVE"}:
        publication_status = "SUSPENDED" if action == "SUSPEND" else "UNPUBLISHED"
        await db.staff_property_reviews.update_one({"subject_ref": item["reference"]}, {"$set": {"publication_status": publication_status, "updated_at": timestamp}})
    event = await _audit(user, "property_listing", listing_reference, action, previous, new_status,
                         payload.reason, payload.notes, {"availability": payload.availability})
    return {"ok": True, "status": new_status, "audit_event": event}
