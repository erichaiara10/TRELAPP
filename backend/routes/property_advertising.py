"""Staff Property Advertising workspace APIs (S-series).

The collections are deliberately separate from the public property catalogue:
staff review must complete before a submission can create or alter a public
listing. Every workflow mutation also appends an immutable audit event.

This module implements the TRELPNG identification rules for duplicate
detection at submission time, the full advertiser + staff workflow state
machine, dedicated per-record endpoints for S02B/S03B/S03C/S07A/S08A/S09A
and the advertiser return loop (messages + resubmit_corrected).

Design notes
------------
* `DraftDataV1` is a per-A-series-stage validated schema (extra fields
  are dropped by Pydantic).  Server always derives owner_user_id from the
  bearer token — client-supplied owner fields are silently discarded.
* `TRANSITIONS[record_type][action]` centralises the state machine.  All
  named dedicated endpoints (identity, conflict, authority, publication,
  exact-location, lifecycle) route through `_apply_transition` so audit
  behaviour, notifications and optimistic concurrency are identical.
* Duplicate detection NEVER auto-merges.  When candidates are found the
  submission is parked in `Conflict Review` and a `pa_conflicts` row is
  created for staff resolution.  One Master Property may host multiple
  simultaneous listings (e.g. sale + rent).
* Lifecycle: a NOT_SEEN / disappearing listing is NEVER auto-classified
  as SOLD/RENTED.  `mark_SOLD_CONFIRMED` and `mark_RENTED_CONFIRMED` are
  the only paths into those states and require an explicit staff call.
"""
from __future__ import annotations

import re
from copy import deepcopy
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo import ReturnDocument

from core.db import db, new_id, now_iso
from core.security import get_current_user, require_roles

router = APIRouter(prefix="/property-advertising", tags=["property-advertising"])
staff_user = require_roles("managing_director", "sales_agent", "leasing_agent", "marketing_officer")


# ---------------------------------------------------------------------------
# Static demo seed rows.  These populate the S-series tables on first boot
# so the UI has something to render before real advertisers submit.  Real
# records inserted via /advertiser/drafts/current/submit coexist with them.
# ---------------------------------------------------------------------------
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
# Column offset of the workflow status in each row-array.
STATUS_INDEX = {"advertiser": 7, "submission": 10, "publication": 11, "location_request": 9, "lifecycle": 12}


# ---------------------------------------------------------------------------
# Workflow state machine — every mutation goes through _apply_transition.
# `notify=True` enqueues a pa_notifications row visible to the advertiser.
# ---------------------------------------------------------------------------
TRANSITIONS = {
    "advertiser": {
        "request_documents": {"to": "Documents Requested", "notify": True},
        "request_resubmission": {"to": "Resubmission Required", "notify": True},
        "reject_identity": {"to": "Restricted", "notify": True},
        "verify_identity": {"to": "Active", "notify": True},
    },
    "submission": {
        "request_clarification": {"to": "Information Required", "notify": True},
        "return_for_correction": {"to": "Changes Required", "notify": True},
        "return_for_changes": {"to": "Changes Required", "notify": True},        # legacy alias
        "confirm_new_property": {"to": "Ready", "notify": True},
        "link_to_existing_master": {"to": "Ready", "notify": True},
        "link_master_property": {"to": "Ready", "notify": True},                 # legacy alias
        "reject_invalid": {"to": "Rejected", "notify": True},
        "resubmit_corrected": {"to": "Submitted", "notify": False},              # advertiser action
        # authority sub-flow
        "request_evidence": {"to": "Information Required", "notify": True},
        "hold_authority": {"to": "Authority On Hold", "notify": False},
        "accept_authority": {"to": "Ready", "notify": True},
        "reject_authority": {"to": "Rejected", "notify": True},
    },
    "publication": {
        "return": {"to": "Changes Required", "notify": True},
        "return_for_changes": {"to": "Changes Required", "notify": True},         # alias
        "publish": {"to": "Published", "notify": True},
        "republish": {"to": "Published", "notify": True},
        "unpublish": {"to": "Unpublished", "notify": True},
        "suspend": {"to": "Suspended", "notify": True},
        "withdraw": {"to": "Withdrawn", "notify": True},
    },
    "location_request": {
        "receive_request": {"to": "Pending Review", "notify": False},
        "request_information": {"to": "Information Required", "notify": True},
        "request_more_info": {"to": "Information Required", "notify": True},      # alias
        "send_to_advertiser": {"to": "Awaiting Advertiser", "notify": True},
        "arrange_inspection": {"to": "Inspection Arranged", "notify": True},
        "decline": {"to": "Declined", "notify": True},
        "decline_request": {"to": "Declined", "notify": True},                     # alias
        "share_location": {"to": "Active", "notify": True},
        "approve_secure_sharing": {"to": "Active", "notify": True},                # alias
    },
    "lifecycle": {
        "send_confirmation": {"to": "Awaiting Advertiser", "notify": True},
        "record_response": {"to": "Current", "notify": False},
        "mark_ACTIVE": {"to": "ACTIVE", "notify": False},
        "mark_NOT_SEEN": {"to": "NOT_SEEN", "notify": False},
        "mark_REMOVED": {"to": "REMOVED", "notify": True},
        "mark_INACTIVE": {"to": "INACTIVE", "notify": True},
        # Terminal confirmed states — reachable ONLY via explicit staff action.
        # Nothing anywhere in the codebase auto-transitions into these.
        "mark_SOLD_CONFIRMED": {"to": "SOLD_CONFIRMED", "notify": True},
        "mark_RENTED_CONFIRMED": {"to": "RENTED_CONFIRMED", "notify": True},
        "suspend": {"to": "Suspended", "notify": True},
        "withdraw": {"to": "Withdrawn", "notify": True},
        "archive": {"to": "Archived", "notify": False},
        "relist": {"to": "Active", "notify": True},
    },
}


# ---------------------------------------------------------------------------
# Validated per-A-series-stage draft schema.  Extra fields are dropped by
# Pydantic — this is how `owner_user_id` / `id` / `reference` submitted by
# a client are silently discarded before ever reaching the database.
# ---------------------------------------------------------------------------
PropertyClass = Literal[
    "urban_residential", "urban_commercial", "urban_vacant_land",
    "customary_vacant_land", "apartment_unit",
]


class DraftDataV1(BaseModel):
    # Stage 1 — Property + transaction type
    listing_type: Optional[Literal["sale", "rent", "sale_and_rent"]] = None
    service: Optional[str] = Field(default=None, max_length=80)
    relationship: Optional[str] = Field(default=None, max_length=80)
    # Stage 2 — Property class / type / parent identity
    property_class: Optional[PropertyClass] = None
    property_type: Optional[str] = Field(default=None, max_length=80)
    parent_building_name: Optional[str] = Field(default=None, max_length=200)
    parent_master_property_id: Optional[str] = Field(default=None, max_length=80)
    # Stage 3 — Location + identifiers
    province: Optional[str] = Field(default=None, max_length=120)
    city: Optional[str] = Field(default=None, max_length=120)
    district: Optional[str] = Field(default=None, max_length=120)
    suburb: Optional[str] = Field(default=None, max_length=120)
    lot: Optional[str] = Field(default=None, max_length=40)
    section: Optional[str] = Field(default=None, max_length=40)
    street: Optional[str] = Field(default=None, max_length=200)
    portion: Optional[str] = Field(default=None, max_length=40)
    map_coords: Optional[str] = Field(default=None, max_length=120)
    # Stage 4 — Price + features
    title: Optional[str] = Field(default=None, max_length=200)
    price: Optional[str] = Field(default=None, max_length=40)
    price_kind: Optional[Literal["fixed", "negotiable", "from", "range"]] = None
    price_max: Optional[str] = Field(default=None, max_length=40)
    bedrooms: Optional[int] = Field(default=None, ge=0, le=99)
    bathrooms: Optional[int] = Field(default=None, ge=0, le=99)
    parking: Optional[int] = Field(default=None, ge=0, le=99)
    area_sqm: Optional[float] = Field(default=None, ge=0)
    building_area_sqm: Optional[float] = Field(default=None, ge=0)
    features: Optional[List[str]] = Field(default=None, max_length=50)
    condition: Optional[
        Literal["new_renovated", "good", "average", "poor_renovation_required"]
    ] = None
    description: Optional[str] = Field(default=None, max_length=5000)
    # Stage 5 — Photos + documents. Counts remain for backward compatibility;
    # server-validated file IDs are the source of truth.
    photos: Optional[int] = Field(default=None, ge=0, le=20)
    documents: Optional[int] = Field(default=None, ge=0, le=10)
    photo_file_ids: Optional[List[str]] = Field(default_factory=list, max_length=20)
    document_file_ids: Optional[List[str]] = Field(default_factory=list, max_length=10)
    # Stage 6 — Declarations
    authority_confirmed: Optional[bool] = None
    terms_accepted: Optional[bool] = None
    authority_evidence: Optional[str] = Field(default=None, max_length=1000)
    # Owner name shown to staff.  Server-derived owner_user_id supersedes this.
    owner_name: Optional[str] = Field(default=None, max_length=200)

    model_config = {"extra": "ignore"}


class AdvertiserDraftIn(BaseModel):
    data: DraftDataV1
    current_step: int = Field(default=1, ge=1, le=8)


class WorkflowAction(BaseModel):
    record_type: Literal["advertiser", "submission", "publication", "location_request", "lifecycle"]
    reference: str = Field(min_length=3, max_length=80)
    action: str = Field(min_length=2, max_length=80)
    reason: Optional[str] = Field(default=None, max_length=1000)


class ConflictResolutionIn(BaseModel):
    resolution: Literal["link_to_master", "confirm_new", "dismiss"]
    master_property_id: Optional[str] = Field(default=None, max_length=80)
    reason: Optional[str] = Field(default=None, max_length=1000)


class ScopedActionIn(BaseModel):
    """Body for the dedicated S02B/S03C/S07A/S08A/S09A endpoints."""
    action: str = Field(min_length=2, max_length=80)
    reason: Optional[str] = Field(default=None, max_length=1000)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
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
    row = [reference, user.get("name") or user.get("email"), "Owner", "Verified",
           "Not started", "0", "Today", "Active", "Unassigned"]
    doc = {
        "id": new_id(), "reference": reference, "owner_user_id": user["id"],
        "email": user.get("email"), "row": row,
        "identity_documents": [], "identity_status": "Not started",
        "created_at": now_iso(), "updated_at": now_iso(),
    }
    await db.pa_advertisers.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


def validate_submission(data: DraftDataV1):
    """Enforce required fields at submission time and identify missing declarations clearly."""
    fields_required = {
        "listing_type": "Sale or Rent", "service": "TREL service",
        "relationship": "Relationship", "property_class": "Property category",
        "property_type": "Property type", "title": "Property title",
        "price": "Price", "description": "Description",
        "province": "Province", "city": "City / Town", "suburb": "Suburb",
    }
    missing = [label for key, label in fields_required.items() if not str(getattr(data, key) or "").strip()]
    if missing:
        raise HTTPException(400, f"Complete these required fields: {', '.join(missing)}")

    # Class-specific identifier requirements.
    if data.property_class in {"urban_residential", "urban_commercial",
                               "urban_vacant_land", "apartment_unit"}:
        for key, label in (("lot", "Lot number"), ("section", "Section number")):
            if not str(getattr(data, key) or "").strip():
                raise HTTPException(400, f"Complete these required fields: {label}")
    if data.property_class == "customary_vacant_land":
        if not str(data.portion or "").strip():
            raise HTTPException(400, "Complete these required fields: Portion number")
        if not str(data.district or "").strip():
            raise HTTPException(400, "Complete these required fields: District")

    price = str(data.price or "").replace("PGK", "").replace(",", "").strip()
    try:
        if float(price) <= 0:
            raise ValueError
    except ValueError:
        raise HTTPException(400, "Price must be greater than zero")

    if not data.authority_confirmed:
        raise HTTPException(
            400, "Authority declaration must be accepted before submission",
        )
    if not data.terms_accepted:
        raise HTTPException(
            400, "Terms & conditions declaration must be accepted before submission",
        )


# ---------------------------------------------------------------------------
# Duplicate detection — TRELPNG identification rules.
# Rules:
#   * urban_residential / urban_commercial / urban_vacant_land: match on
#     owner + lot + section + street + suburb + province.
#   * customary_vacant_land: match on owner + portion + district + province.
#   * Vacant land is compared ONLY with other vacant land.
#   * apartment_unit: NEVER auto-merged with the parent building; require an
#     explicit parent_master_property_id from staff.  Any tentative match on
#     the shared parcel is surfaced as a REVIEW case, not a merge.
#   * Same owner + same parcel = duplicate candidate.  A sale + rent pair
#     on the SAME master property is allowed (one master, many listings) —
#     it is not treated as a duplicate.
# ---------------------------------------------------------------------------
def _norm(v: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (v or "").strip().casefold())


def _class_of_master(mp: dict) -> str:
    """Return one of {urban, customary, vacant_urban, vacant_customary, apartment}."""
    subtype = _norm(mp.get("property_subtype") or mp.get("property_class"))
    if "customary" in subtype:
        return "vacant_customary"
    if "vacant" in subtype and "customary" not in subtype:
        return "vacant_urban"
    if "apartment" in subtype or "unit" in subtype:
        return "apartment"
    return "urban"


async def find_potential_matches(
    data: DraftDataV1, owner_user_id: str,
) -> List[dict]:
    """Return possible master_property candidates for the submission.

    TRELPNG confirmed rules:
      * Urban/town property: match when Lot + Section + suburb/location are
        the same.  Owner, street and province are NOT required for the
        match (owner may be shown as supporting evidence only).
      * Large / customary vacant land: match when Portion + location +
        district + province are the same.  Owner is supporting evidence
        only and is not required for the match.
      * Vacant land is compared ONLY with other vacant land.
      * Apartments / units + commercial premises: same-parcel candidates
        are surfaced for staff review — never silently merged with the
        parent building.
      * Values are normalised (case-fold + whitespace-collapse) before
        comparison so 'Boroko ' vs 'boroko' vs 'BOROKO' all match.

    NEVER auto-merges — returns candidates for the S03B UI.
    """
    if data.property_class is None:
        return []
    n = _norm

    # ---- Customary vacant land: portion + location + district + province ----
    if data.property_class == "customary_vacant_land":
        if not (data.portion and data.district and data.province):
            return []
        # Broad query on portion; normalise the remaining fields in Python
        # so 'Sohe ' vs 'sohe' match.
        candidates = await db.master_properties.find(
            {"portion_number": {"$regex": f"^{re.escape(data.portion.strip())}$",
                                 "$options": "i"}},
            {"_id": 0},
        ).to_list(50)
        results = []
        subject_location = n(data.city or data.district)
        for c in candidates:
            # Vacant with vacant only.
            if _class_of_master(c) not in {"vacant_customary", "vacant_urban"}:
                continue
            # location: master.city OR master.suburb OR master.local_area.
            location_ok = subject_location in {
                n(c.get("city")), n(c.get("suburb")), n(c.get("local_area")),
            }
            if not location_ok:
                continue
            # district: master.local_area OR master.city.
            district_ok = n(data.district) in {
                n(c.get("local_area")), n(c.get("city")),
            }
            if not district_ok:
                continue
            if n(c.get("province")) != n(data.province):
                continue
            owner_hint = (c.get("canonical_fields") or {}).get("owner_name") or ""
            results.append({
                "master_property_id": c["id"],
                "reason": "Same portion, location, district and province",
                "matched_fields": ["portion", "location", "district", "province"],
                "owner_evidence": owner_hint,   # supporting evidence only
            })
        return results

    # ---- Urban / apartment / urban vacant land: lot + section + suburb ONLY ----
    if data.property_class in {"urban_residential", "urban_commercial",
                               "urban_vacant_land", "apartment_unit"}:
        if not (data.lot and data.section and data.suburb):
            return []
        # Case-insensitive query on lot + section; post-filter suburb in
        # Python so we honour the full normalisation contract.
        candidates = await db.master_properties.find(
            {"allotment_number": {"$regex": f"^{re.escape(data.lot.strip())}$",
                                    "$options": "i"},
             "section_number": {"$regex": f"^{re.escape(data.section.strip())}$",
                                 "$options": "i"}},
            {"_id": 0},
        ).to_list(50)
        results = []
        subject_suburb = n(data.suburb)
        for c in candidates:
            cclass = _class_of_master(c)
            # Vacant land compared with vacant land only.
            if data.property_class == "urban_vacant_land" and cclass not in {
                "vacant_urban", "vacant_customary",
            }:
                continue
            if data.property_class != "urban_vacant_land" and cclass in {
                "vacant_urban", "vacant_customary",
            }:
                continue
            if n(c.get("suburb")) != subject_suburb:
                continue
            # Apartments / commercial: surface for staff review, never merge.
            if data.property_class == "apartment_unit":
                reason = ("Same parcel — unit-level identity requires staff to link "
                           "to the correct parent building or confirm a new unit")
            else:
                reason = "Same lot, section and suburb"
            owner_hint = (c.get("canonical_fields") or {}).get("owner_name") or ""
            results.append({
                "master_property_id": c["id"],
                "reason": reason,
                "matched_fields": ["lot", "section", "suburb"],
                "owner_evidence": owner_hint,   # supporting evidence only
            })
        return results

    return []


async def _create_master_property(data: DraftDataV1, submission_reference: str) -> str:
    """Create a Master Property row from a confirmed submission.  Returns id."""
    now = now_iso()
    subtype = data.property_type or ""
    property_class = "vacant_land" if data.property_class in {
        "urban_vacant_land", "customary_vacant_land",
    } else ("commercial_industrial" if data.property_class == "urban_commercial" else "residential")
    doc = {
        "id": new_id(),
        "property_class": property_class,
        "property_subtype": subtype,
        "allotment_number": data.lot,
        "section_number": data.section,
        "portion_number": data.portion,
        "street": data.street,
        "suburb": data.suburb,
        "local_area": data.district,
        "city": data.city,
        "province": data.province,
        "building_name": data.parent_building_name,
        "canonical_fields": {"provenance": "advertiser_submission",
                             "submission_reference": submission_reference},
        "trel_property_id": None,
        "algorithm_version": "MATCH-1.0",
        "created_at": now,
        "updated_at": now,
    }
    await db.master_properties.insert_one(doc)
    return doc["id"]


# ---------------------------------------------------------------------------
# Advertiser endpoints
# ---------------------------------------------------------------------------
@router.get("/advertiser/me")
async def advertiser_me(user: dict = Depends(get_current_user)):
    require_advertiser(user)
    return await ensure_advertiser(user)


@router.get("/advertiser/dashboard")
async def advertiser_dashboard(user: dict = Depends(get_current_user)):
    """Account-scoped A01 dashboard. Never returns another advertiser's data."""
    require_advertiser(user)
    advertiser = await ensure_advertiser(user)
    owner_user_id = user["id"]

    submissions = await db.pa_submissions.find(
        {"owner_user_id": owner_user_id}, {"_id": 0},
    ).sort("updated_at", -1).to_list(500)
    drafts = await db.pa_drafts.find(
        {"owner_user_id": owner_user_id, "status": "draft"}, {"_id": 0},
    ).sort("updated_at", -1).to_list(50)
    references = [item["reference"] for item in submissions if item.get("reference")]

    active_statuses = {"Published", "Active", "Available"}
    review_statuses = {
        "Submitted", "Under Review", "Conflict Review", "Ready",
        "Pending review", "Authority Review",
    }
    returned_statuses = {
        "Changes Required", "Information Required",
        "Resubmission Required", "Documents Requested",
    }

    listing_items = []
    for item in submissions:
        data = item.get("data") or {}
        listing_items.append({
            "reference": item.get("reference"),
            "title": data.get("title") or item.get("reference"),
            "location": ", ".join(filter(None, [
                data.get("suburb") or data.get("city"),
                data.get("province"),
            ])),
            "price": data.get("price"),
            "listing_type": data.get("listing_type"),
            "status": item.get("status") or (item.get("row") or [None] * 11)[10],
            "updated_at": item.get("updated_at"),
            "cover_file_id": (data.get("photo_file_ids") or [None])[0],
        })
    for item in drafts:
        data = item.get("data") or {}
        listing_items.append({
            "reference": item.get("id"),
            "title": data.get("title") or "Untitled draft",
            "location": ", ".join(filter(None, [
                data.get("suburb") or data.get("city"),
                data.get("province"),
            ])),
            "price": data.get("price"),
            "listing_type": data.get("listing_type"),
            "status": "Draft",
            "updated_at": item.get("updated_at"),
            "cover_file_id": (data.get("photo_file_ids") or [None])[0],
        })
    listing_items.sort(key=lambda item: item.get("updated_at") or "", reverse=True)

    audit_query = {
        "$or": [
            {"performed_by_id": owner_user_id},
            {"reference": {"$in": references}},
        ],
    } if references else {"performed_by_id": owner_user_id}
    audit_events = await db.pa_audit.find(
        audit_query,
        {
            "_id": 0, "performed_by_id": 0, "requested_by_id": 0,
        },
    ).sort("created_at", -1).to_list(10)
    title_by_reference = {
        item.get("reference"): (item.get("data") or {}).get("title")
        for item in submissions
    }
    activity = [{
        "id": event.get("id"),
        "reference": event.get("reference"),
        "title": title_by_reference.get(event.get("reference")) or event.get("reference"),
        "action": event.get("action"),
        "status": event.get("new_status"),
        "created_at": event.get("created_at"),
    } for event in audit_events]

    reminders = []
    if advertiser.get("identity_status") not in {"Verified", "Active"}:
        reminders.append({
            "kind": "identity",
            "title": "Verify your identity",
            "detail": "One valid government-issued ID is required.",
            "target": "/advertiser/account-settings",
        })
    returned = [item for item in submissions if item.get("status") in returned_statuses]
    if returned:
        reminders.append({
            "kind": "changes",
            "title": "Property information required",
            "detail": f"{len(returned)} submission(s) require your response.",
            "target": "/advertiser/properties",
        })
    draft_without_files = [
        item for item in drafts
        if not ((item.get("data") or {}).get("photo_file_ids") or [])
    ]
    if draft_without_files:
        reminders.append({
            "kind": "photos",
            "title": "Add property photos",
            "detail": f"{len(draft_without_files)} draft(s) have no property photos.",
            "target": "/advertiser/add-property/photos",
        })

    enquiries_count = await db.pa_enquiries.count_documents(
        {"owner_user_id": owner_user_id},
    )
    inspections = await db.pa_location_requests.find(
        {"owner_user_id": owner_user_id}, {"_id": 0, "requested_by_id": 0},
    ).sort("created_at", -1).to_list(5)

    location_data = {}
    if submissions:
        location_data = submissions[0].get("data") or {}
    elif drafts:
        location_data = drafts[0].get("data") or {}

    return {
        "advertiser": {
            "reference": advertiser.get("reference"),
            "name": user.get("name") or (advertiser.get("row") or [None, user.get("email")])[1],
            "email": user.get("email"),
            "identity_status": advertiser.get("identity_status", "Not started"),
            "location": ", ".join(filter(None, [
                location_data.get("city") or location_data.get("suburb"),
                location_data.get("province"),
            ])),
        },
        "metrics": {
            "active_listings": sum(
                1 for item in submissions if item.get("status") in active_statuses
            ),
            "draft_listings": len(drafts),
            "awaiting_review": sum(
                1 for item in submissions if item.get("status") in review_statuses
            ),
            "total_enquiries": enquiries_count,
        },
        "listings": listing_items[:10],
        "recent_activity": activity,
        "reminders": reminders,
        "inspections": inspections,
        "capabilities": {
            "enquiries": enquiries_count > 0,
            "inspections": bool(inspections),
        },
    }


@router.get("/advertiser/drafts/current")
async def current_draft(user: dict = Depends(get_current_user)):
    require_advertiser(user)
    await ensure_advertiser(user)
    return await db.pa_drafts.find_one({"owner_user_id": user["id"], "status": "draft"}, {"_id": 0})


async def _persist_draft(payload: AdvertiserDraftIn, user: dict, advertiser: dict) -> dict:
    now = now_iso()
    data = payload.data.model_dump(exclude_none=False)
    existing = await db.pa_drafts.find_one(
        {"owner_user_id": user["id"], "status": "draft"}, {"_id": 0},
    )
    if existing:
        await db.pa_drafts.update_one(
            {"id": existing["id"], "owner_user_id": user["id"]},
            {"$set": {"data": data, "current_step": payload.current_step, "updated_at": now}},
        )
        draft_id = existing["id"]
    else:
        draft_id = new_id()
        await db.pa_drafts.insert_one({
            "id": draft_id, "owner_user_id": user["id"],
            "advertiser_reference": advertiser["reference"],
            "status": "draft", "data": data, "current_step": payload.current_step,
            "created_at": now, "updated_at": now,
        })
    return await db.pa_drafts.find_one({"id": draft_id}, {"_id": 0})


@router.put("/advertiser/drafts/current")
async def save_draft(payload: AdvertiserDraftIn, user: dict = Depends(get_current_user)):
    require_advertiser(user)
    await validate_attachment_ids(payload.data, user["id"])
    advertiser = await ensure_advertiser(user)
    return await _persist_draft(payload, user, advertiser)


async def validate_attachment_ids(
    data: DraftDataV1, owner_user_id: str, submission_reference: Optional[str] = None,
) -> List[str]:
    """Verify every attachment belongs to this advertiser and has the right category."""
    photo_ids = list(dict.fromkeys(data.photo_file_ids or []))
    document_ids = list(dict.fromkeys(data.document_file_ids or []))
    all_ids = photo_ids + document_ids
    if not all_ids:
        data.photos = 0
        data.documents = 0
        return []

    records = await db.files.find({
        "id": {"$in": all_ids},
        "owner_user_id": owner_user_id,
        "scope": "property_advertising",
        "is_deleted": False,
    }, {"_id": 0, "id": 1, "category": 1, "submission_reference": 1}).to_list(50)
    by_id = {record["id"]: record for record in records}
    if set(by_id) != set(all_ids):
        raise HTTPException(400, "One or more attached files are missing or not owned by this advertiser")
    for file_id in photo_ids:
        if by_id[file_id].get("category") != "photo":
            raise HTTPException(400, "A document cannot be attached as a property photo")
    for file_id in document_ids:
        if by_id[file_id].get("category") != "document":
            raise HTTPException(400, "A property photo cannot be attached as a document")
    for record in records:
        bound_reference = record.get("submission_reference")
        if bound_reference and bound_reference != submission_reference:
            raise HTTPException(400, "An attached file already belongs to another submission")

    data.photo_file_ids = photo_ids
    data.document_file_ids = document_ids
    data.photos = len(photo_ids)
    data.documents = len(document_ids)
    return all_ids


@router.post("/advertiser/drafts/current/submit")
async def submit_draft(payload: AdvertiserDraftIn, user: dict = Depends(get_current_user)):
    require_advertiser(user)
    validate_submission(payload.data)
    advertiser = await ensure_advertiser(user)
    saved = await _persist_draft(payload, user, advertiser)
    reference = await next_reference("submission", "TREL-", 11000)
    now = now_iso()
    data = payload.data
    attachment_ids = await validate_attachment_ids(data, user["id"])
    matches = await find_potential_matches(data, user["id"])
    status = "Conflict Review" if matches else "Submitted"

    row = [
        reference, data.title, user.get("name") or user.get("email"),
        data.relationship, data.service, "Today", "Within 3 days", "On time",
        ("Possible" if matches else "Clear"), "Unassigned", status,
    ]
    submission = {
        "id": new_id(), "reference": reference, "owner_user_id": user["id"],
        "advertiser_reference": advertiser["reference"], "draft_id": saved["id"],
        "data": data.model_dump(exclude_none=False), "row": row, "status": status,
        "master_property_id": None, "potential_matches": matches,
        "created_at": now, "updated_at": now,
    }
    await db.pa_submissions.insert_one(submission)
    if attachment_ids:
        await db.files.update_many(
            {
                "id": {"$in": attachment_ids},
                "owner_user_id": user["id"],
                "scope": "property_advertising",
                "is_deleted": False,
            },
            {"$set": {
                "submission_reference": reference,
                "draft_id": saved["id"],
                "updated_at": now,
            }},
        )
    await db.pa_drafts.update_one(
        {"id": saved["id"], "owner_user_id": user["id"]},
        {"$set": {"status": "submitted", "submission_reference": reference, "updated_at": now}},
    )
    await db.pa_advertisers.update_one(
        {"owner_user_id": user["id"]},
        {"$inc": {"submission_count": 1}, "$set": {"updated_at": now}},
    )
    await db.pa_audit.insert_one({
        "id": new_id(), "record_type": "submission", "reference": reference,
        "action": "submit", "previous_status": "Draft", "new_status": status,
        "reason": "Advertiser submitted property",
        "performed_by_id": user["id"],
        "performed_by_name": user.get("name") or user.get("email"),
        "channel": "advertiser_workspace", "created_at": now,
    })
    if matches:
        conflict_id = new_id()
        await db.pa_conflicts.insert_one({
            "id": conflict_id, "reference": reference,
            "submission_reference": reference,
            "owner_user_id": user["id"],
            "candidates": matches,
            "status": "open",
            "resolved_master_property_id": None,
            "resolution_reason": None,
            "created_at": now, "updated_at": now,
        })
        await db.pa_audit.insert_one({
            "id": new_id(), "record_type": "submission", "reference": reference,
            "action": "flag_conflict", "previous_status": "Draft",
            "new_status": "Conflict Review",
            "reason": f"{len(matches)} potential master-property match(es) detected",
            "performed_by_id": "system",
            "performed_by_name": "Duplicate detection",
            "channel": "system", "created_at": now,
        })
    return {k: v for k, v in submission.items() if k != "_id"}


@router.get("/advertiser/submissions")
async def advertiser_submissions(user: dict = Depends(get_current_user)):
    require_advertiser(user)
    return await db.pa_submissions.find(
        {"owner_user_id": user["id"]}, {"_id": 0},
    ).sort("created_at", -1).to_list(500)


@router.get("/advertiser/submissions/{reference}")
async def advertiser_submission_detail(reference: str, user: dict = Depends(get_current_user)):
    """Advertiser's view of one of their submissions PLUS staff messages
    that were sent to them.  Internal staff-only notes are hidden."""
    require_advertiser(user)
    doc = await db.pa_submissions.find_one(
        {"reference": reference, "owner_user_id": user["id"]}, {"_id": 0},
    )
    if not doc:
        raise HTTPException(404, "Submission not found")
    # Staff messages = pa_notifications rows targeted at this advertiser for this submission.
    messages = await db.pa_notifications.find(
        {"recipient_user_id": user["id"], "reference": reference,
         "visibility": {"$ne": "staff_only"}},
        {"_id": 0, "requested_by_id": 0},   # hide internal staff id
    ).sort("created_at", -1).to_list(200)
    return {**doc, "messages": messages}


class ResubmitIn(BaseModel):
    data: DraftDataV1
    reason: Optional[str] = Field(default=None, max_length=1000)


@router.post("/advertiser/submissions/{reference}/resubmit")
async def resubmit_corrected(reference: str, payload: ResubmitIn,
                             user: dict = Depends(get_current_user)):
    """Advertiser return loop — patch a returned submission and re-submit it
    WITHOUT losing the original TREL- reference or draft_id."""
    require_advertiser(user)
    doc = await db.pa_submissions.find_one(
        {"reference": reference, "owner_user_id": user["id"]}, {"_id": 0},
    )
    if not doc:
        raise HTTPException(404, "Submission not found")
    if doc["status"] not in {"Changes Required", "Information Required",
                             "Resubmission Required", "Documents Requested"}:
        raise HTTPException(
            400, f"Submission is in status '{doc['status']}' — no correction expected",
        )
    validate_submission(payload.data)
    attachment_ids = await validate_attachment_ids(payload.data, user["id"], reference)
    now = now_iso()
    matches = await find_potential_matches(payload.data, user["id"])
    new_status = "Conflict Review" if matches else "Submitted"
    row = list(doc["row"])
    row[1] = payload.data.title
    row[STATUS_INDEX["submission"]] = new_status
    row[8] = "Possible" if matches else "Clear"
    result = await db.pa_submissions.update_one(
        {"reference": reference, "updated_at": doc["updated_at"]},
        {"$set": {
            "data": payload.data.model_dump(exclude_none=False),
            "row": row, "status": new_status,
            "potential_matches": matches, "updated_at": now,
        }},
    )
    if result.modified_count != 1:
        raise HTTPException(409, "Submission changed while you were correcting it")
    if attachment_ids:
        await db.files.update_many(
            {
                "id": {"$in": attachment_ids},
                "owner_user_id": user["id"],
                "scope": "property_advertising",
                "is_deleted": False,
            },
            {"$set": {
                "submission_reference": reference,
                "draft_id": doc.get("draft_id"),
                "updated_at": now,
            }},
        )
    await db.pa_audit.insert_one({
        "id": new_id(), "record_type": "submission", "reference": reference,
        "action": "resubmit_corrected", "previous_status": doc["status"],
        "new_status": new_status, "reason": payload.reason or "Advertiser resubmitted",
        "performed_by_id": user["id"],
        "performed_by_name": user.get("name") or user.get("email"),
        "channel": "advertiser_workspace", "created_at": now,
    })
    return await db.pa_submissions.find_one({"reference": reference}, {"_id": 0})


@router.get("/advertiser/messages")
async def advertiser_messages(user: dict = Depends(get_current_user), limit: int = 100):
    """Advertiser inbox — every notification the system routed to this user.
    Internal staff notes and other advertisers' notifications are excluded."""
    require_advertiser(user)
    limit = max(1, min(limit, 500))
    return await db.pa_notifications.find(
        {"recipient_user_id": user["id"], "visibility": {"$ne": "staff_only"}},
        {"_id": 0, "requested_by_id": 0},
    ).sort("created_at", -1).to_list(limit)


# ---------------------------------------------------------------------------
# Staff endpoints
# ---------------------------------------------------------------------------
async def ensure_seeded():
    """Create representative dev records once; never overwrite real changes."""
    for key, seed_rows in SEED.items():
        collection = db[f"pa_{key}"]
        for row in seed_rows:
            await collection.update_one(
                {"reference": row[0]},
                {"$setOnInsert": {"id": new_id(), "reference": row[0],
                                  "row": deepcopy(row),
                                  "created_at": now_iso(), "updated_at": now_iso()}},
                upsert=True,
            )


async def _rows(collection_name: str):
    docs = await db[collection_name].find({}, {"_id": 0}).sort("created_at", 1).to_list(1000)
    return [doc["row"] for doc in docs]


@router.get("/workspace")
async def workspace(user: dict = Depends(staff_user)):
    await ensure_seeded()
    return {
        "advertisers": await _rows("pa_advertisers"),
        "submissions": await _rows("pa_submissions"),
        "publications": await _rows("pa_publications"),
        "location_requests": await _rows("pa_location_requests"),
        "lifecycle": await _rows("pa_lifecycle"),
    }


async def _apply_transition(record_type: str, reference: str, action: str,
                             reason: Optional[str], user: dict,
                             extra_updates: Optional[dict] = None) -> dict:
    """Central state-machine entry.  Every dedicated endpoint routes here so
    audit + notifications + optimistic-concurrency behaviour is uniform."""
    transitions = TRANSITIONS.get(record_type) or {}
    rule = transitions.get(action)
    if not rule:
        raise HTTPException(400, "Action is not allowed for this record type")
    collection = db[COLLECTIONS[record_type]]
    doc = await collection.find_one({"reference": reference}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Property-advertising record not found")
    row = list(doc["row"])
    status_index = STATUS_INDEX[record_type]
    previous_status = row[status_index]
    new_status = rule["to"]
    row[status_index] = new_status
    timestamp = now_iso()
    update_set = {"row": row, "status": new_status, "updated_at": timestamp}
    if extra_updates:
        update_set.update(extra_updates)
    result = await collection.update_one(
        {"reference": reference, "updated_at": doc["updated_at"]},
        {"$set": update_set},
    )
    if result.modified_count != 1:
        raise HTTPException(409, "Record changed while you were reviewing it; refresh and retry")
    audit = {
        "id": new_id(), "record_type": record_type, "reference": reference,
        "action": action, "previous_status": previous_status,
        "new_status": new_status, "reason": reason or "",
        "performed_by_id": user["id"],
        "performed_by_name": user.get("name") or user.get("email"),
        "performed_by_role": user.get("role"),
        "channel": "staff_workspace", "created_at": timestamp,
    }
    await db.pa_audit.insert_one(audit)
    if rule.get("notify") and doc.get("owner_user_id"):
        await db.pa_notifications.insert_one({
            "id": new_id(), "record_type": record_type, "reference": reference,
            "action": action, "status": "queued", "channels": ["inbox", "email"],
            "requested_by_id": user["id"],
            "recipient_user_id": doc["owner_user_id"],
            "visibility": "advertiser",
            "summary": reason or f"{action} on {reference}",
            "created_at": timestamp,
        })
    return {
        "ok": True,
        "record": {**doc, "row": row, "status": new_status, "updated_at": timestamp,
                   **(extra_updates or {})},
        "audit": {k: v for k, v in audit.items() if k != "_id"},
    }


@router.post("/actions")
async def apply_action(payload: WorkflowAction, user: dict = Depends(staff_user)):
    """Generic staff action endpoint — kept for backward compat.  Dedicated
    per-record endpoints (S02B/S03B/S03C/S07A/S08A/S09A below) also route
    through _apply_transition so behaviour is identical."""
    await ensure_seeded()
    return await _apply_transition(payload.record_type, payload.reference,
                                    payload.action, payload.reason, user)


# ---------------------------------------------------------------------------
# S02B — Identity verification (dedicated)
# ---------------------------------------------------------------------------
class IdentityDocumentIn(BaseModel):
    kind: Literal["passport", "driver_licence", "nid_card", "other"] = "other"
    filename: str = Field(min_length=1, max_length=200)
    note: Optional[str] = Field(default=None, max_length=500)
    # NOTE: real file bytes handled by a future storage endpoint.  This
    # endpoint records the metadata + advertiser's stated identity so
    # staff can review.  Only ONE valid gov ID is required.


@router.get("/advertisers/{reference}/identity")
async def identity_read(reference: str, user: dict = Depends(get_current_user)):
    """Advertiser can read their own identity record; staff can read any."""
    doc = await db.pa_advertisers.find_one({"reference": reference}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Advertiser not found")
    is_staff = user.get("role") in {
        "system_admin", "managing_director", "sales_agent",
        "leasing_agent", "marketing_officer",
    }
    if not is_staff and doc.get("owner_user_id") != user["id"]:
        raise HTTPException(403, "Not your advertiser record")
    return {
        "reference": reference,
        "identity_status": doc.get("identity_status", "Not started"),
        "documents": doc.get("identity_documents", []),
    }


@router.post("/advertisers/{reference}/identity/documents")
async def identity_upload_document(reference: str, payload: IdentityDocumentIn,
                                    user: dict = Depends(get_current_user)):
    require_advertiser(user)
    doc = await db.pa_advertisers.find_one({"reference": reference}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Advertiser not found")
    if doc.get("owner_user_id") != user["id"]:
        raise HTTPException(403, "Not your advertiser record")
    entry = {
        "id": new_id(), "kind": payload.kind, "filename": payload.filename,
        "note": payload.note or "", "uploaded_at": now_iso(),
    }
    await db.pa_advertisers.update_one(
        {"reference": reference},
        {"$push": {"identity_documents": entry},
         "$set": {"identity_status": "Pending review", "updated_at": now_iso()}},
    )
    await db.pa_audit.insert_one({
        "id": new_id(), "record_type": "advertiser", "reference": reference,
        "action": "upload_identity_document", "previous_status": doc.get("identity_status"),
        "new_status": "Pending review",
        "reason": f"{payload.kind}: {payload.filename}",
        "performed_by_id": user["id"], "performed_by_name": user.get("name") or user.get("email"),
        "channel": "advertiser_workspace", "created_at": now_iso(),
    })
    return {"ok": True, "document": entry}


@router.post("/advertisers/{reference}/identity/decision")
async def identity_decision(reference: str, payload: ScopedActionIn,
                             user: dict = Depends(staff_user)):
    """Staff decisions on advertiser identity: verify_identity /
    request_documents / request_resubmission / reject_identity.
    Confirms only ONE valid gov ID is needed — no combined requirement."""
    if payload.action not in TRANSITIONS["advertiser"]:
        raise HTTPException(400, "Unknown identity decision")
    extra = {"identity_status": TRANSITIONS["advertiser"][payload.action]["to"]}
    return await _apply_transition("advertiser", reference, payload.action,
                                    payload.reason, user, extra)


# ---------------------------------------------------------------------------
# S03B — Conflict resolution (dedicated)
# ---------------------------------------------------------------------------
@router.get("/conflicts/{reference}")
async def conflict_read(reference: str, user: dict = Depends(staff_user)):
    doc = await db.pa_conflicts.find_one({"reference": reference}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Conflict record not found")
    submission = await db.pa_submissions.find_one({"reference": reference}, {"_id": 0})
    return {**doc, "submission": submission}


@router.post("/conflicts/{reference}/resolve")
async def conflict_resolve(reference: str, payload: ConflictResolutionIn,
                            user: dict = Depends(staff_user)):
    conflict = await db.pa_conflicts.find_one({"reference": reference}, {"_id": 0})
    if not conflict:
        raise HTTPException(404, "Conflict record not found")
    if conflict.get("status") != "open":
        raise HTTPException(400, "Conflict is already resolved")
    if payload.resolution == "link_to_master":
        if not payload.master_property_id:
            raise HTTPException(400, "master_property_id is required for link_to_master")
        candidate_ids = {c["master_property_id"] for c in conflict.get("candidates", [])}
        if payload.master_property_id not in candidate_ids:
            raise HTTPException(400, "master_property_id is not a listed candidate")
        # apply state machine — this creates audit + notification.
        result = await _apply_transition(
            "submission", reference, "link_to_existing_master",
            payload.reason, user,
            {"master_property_id": payload.master_property_id},
        )
        await db.pa_conflicts.update_one(
            {"reference": reference},
            {"$set": {"status": "resolved_link",
                      "resolved_master_property_id": payload.master_property_id,
                      "resolution_reason": payload.reason or "Linked to existing master",
                      "resolved_by_id": user["id"], "updated_at": now_iso()}},
        )
        return result
    if payload.resolution == "confirm_new":
        submission = await db.pa_submissions.find_one({"reference": reference}, {"_id": 0})
        if not submission:
            raise HTTPException(404, "Submission not found")
        try:
            data = DraftDataV1(**submission.get("data", {}))
        except Exception:
            data = DraftDataV1()
        master_id = await _create_master_property(data, reference)
        result = await _apply_transition(
            "submission", reference, "confirm_new_property",
            payload.reason, user, {"master_property_id": master_id},
        )
        await db.pa_conflicts.update_one(
            {"reference": reference},
            {"$set": {"status": "resolved_new",
                      "resolved_master_property_id": master_id,
                      "resolution_reason": payload.reason or "Confirmed as a new master property",
                      "resolved_by_id": user["id"], "updated_at": now_iso()}},
        )
        return result
    # dismiss
    await db.pa_conflicts.update_one(
        {"reference": reference},
        {"$set": {"status": "dismissed",
                  "resolution_reason": payload.reason or "Dismissed by staff",
                  "resolved_by_id": user["id"], "updated_at": now_iso()}},
    )
    await db.pa_audit.insert_one({
        "id": new_id(), "record_type": "submission", "reference": reference,
        "action": "dismiss_conflict", "previous_status": "Conflict Review",
        "new_status": "Conflict Review", "reason": payload.reason or "",
        "performed_by_id": user["id"],
        "performed_by_name": user.get("name") or user.get("email"),
        "channel": "staff_workspace", "created_at": now_iso(),
    })
    return {"ok": True, "status": "dismissed"}


# ---------------------------------------------------------------------------
# S03C — Authority review (dedicated)
# ---------------------------------------------------------------------------
@router.get("/authority/{reference}")
async def authority_read(reference: str, user: dict = Depends(staff_user)):
    doc = await db.pa_submissions.find_one({"reference": reference}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Submission not found")
    document_ids = doc.get("data", {}).get("document_file_ids") or []
    documents = await db.files.find(
        {
            "id": {"$in": document_ids},
            "scope": "property_advertising",
            "category": "document",
            "is_deleted": False,
        },
        {"_id": 0, "storage_path": 0, "sha256": 0, "owner_user_id": 0},
    ).sort("created_at", 1).to_list(20) if document_ids else []
    for document in documents:
        document["url"] = f"/api/property-advertising/files/{document['id']}"
    return {
        "reference": reference,
        "relationship": doc.get("data", {}).get("relationship"),
        "authority_evidence": doc.get("data", {}).get("authority_evidence"),
        "authority_confirmed": doc.get("data", {}).get("authority_confirmed"),
        "documents": documents,
        "status": doc.get("status"),
        "audit": await db.pa_audit.find(
            {"record_type": "submission", "reference": reference,
             "action": {"$in": ["request_evidence", "hold_authority",
                                 "accept_authority", "reject_authority"]}},
            {"_id": 0},
        ).sort("created_at", -1).to_list(200),
    }


@router.post("/authority/{reference}/decision")
async def authority_decision(reference: str, payload: ScopedActionIn,
                              user: dict = Depends(staff_user)):
    if payload.action not in {"request_evidence", "hold_authority",
                              "accept_authority", "reject_authority"}:
        raise HTTPException(400, "Unknown authority decision")
    return await _apply_transition("submission", reference, payload.action,
                                    payload.reason, user)


# ---------------------------------------------------------------------------
# S07A — Publication decision (dedicated)
# ---------------------------------------------------------------------------
@router.post("/publications/{reference}/decision")
async def publication_decision(reference: str, payload: ScopedActionIn,
                                user: dict = Depends(staff_user)):
    return await _apply_transition("publication", reference, payload.action,
                                    payload.reason, user)


# ---------------------------------------------------------------------------
# S08A — Exact-location decision (dedicated)
# ---------------------------------------------------------------------------
@router.post("/exact-location/{reference}/decision")
async def exact_location_decision(reference: str, payload: ScopedActionIn,
                                    user: dict = Depends(staff_user)):
    return await _apply_transition("location_request", reference, payload.action,
                                    payload.reason, user)


# ---------------------------------------------------------------------------
# S09A — Lifecycle mark (dedicated)
# ---------------------------------------------------------------------------
@router.post("/lifecycle/{reference}/mark")
async def lifecycle_mark(reference: str, payload: ScopedActionIn,
                          user: dict = Depends(staff_user)):
    return await _apply_transition("lifecycle", reference, payload.action,
                                    payload.reason, user)


# ---------------------------------------------------------------------------
# Read-only audit + notification-outbox (staff)
# ---------------------------------------------------------------------------
@router.get("/audit-events")
async def audit_events(limit: int = 200, user: dict = Depends(staff_user)):
    limit = max(1, min(limit, 1000))
    return await db.pa_audit.find({}, {"_id": 0}).sort("created_at", -1).to_list(limit)


@router.get("/notification-outbox")
async def notification_outbox(limit: int = 200, user: dict = Depends(staff_user)):
    """Read-only staff view of notifications queued for the delivery service."""
    limit = max(1, min(limit, 1000))
    return await db.pa_notifications.find({}, {"_id": 0}).sort("created_at", -1).to_list(limit)


# ---------------------------------------------------------------------------
# Generic record-detail endpoint — MUST be defined AFTER every literal
# `/foo/{reference}` route above so FastAPI does not shadow them.
# ---------------------------------------------------------------------------
@router.get("/{record_type}/{reference}")
async def get_record(record_type: str, reference: str, user: dict = Depends(staff_user)):
    await ensure_seeded()
    collection_name = COLLECTIONS.get(record_type)
    if not collection_name:
        raise HTTPException(404, "Unknown property-advertising record type")
    doc = await db[collection_name].find_one({"reference": reference}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Property-advertising record not found")
    doc["audit"] = await db.pa_audit.find(
        {"record_type": record_type, "reference": reference}, {"_id": 0},
    ).sort("created_at", -1).to_list(500)
    if record_type == "submission":
        attachment_ids = list(dict.fromkeys(
            (doc.get("data", {}).get("photo_file_ids") or [])
            + (doc.get("data", {}).get("document_file_ids") or [])
        ))
        attachments = await db.files.find(
            {
                "id": {"$in": attachment_ids},
                "scope": "property_advertising",
                "is_deleted": False,
            },
            {
                "_id": 0, "storage_path": 0, "sha256": 0,
                "owner_user_id": 0,
            },
        ).sort("created_at", 1).to_list(50) if attachment_ids else []
        for attachment in attachments:
            attachment["url"] = f"/api/property-advertising/files/{attachment['id']}"
        doc["attachments"] = attachments
    return doc
