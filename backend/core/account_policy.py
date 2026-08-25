"""TRELPNG Version 1 account-category and workspace policy."""
from __future__ import annotations

from fastapi import Depends, HTTPException

from core.db import db
from core.security import get_current_user

STAFF = "STAFF"
PROPERTY_ADVERTISER = "PROPERTY_ADVERTISER"
REFERRAL_PARTNER = "REFERRAL_PARTNER"
GUEST = "GUEST"

ACCOUNT_CATEGORIES = {STAFF, PROPERTY_ADVERTISER}
ACTIVE_ACCOUNT_STATUSES = {"ACTIVE"}
PROPERTY_RELATIONSHIPS = {
    "OWNER", "JOINT_OWNER", "AUTHORISED_AGENT", "AUTHORISED_REPRESENTATIVE",
}
GOVERNMENT_ID_TYPES = {"PASSPORT", "DRIVER_LICENCE", "NID_CARD"}
SUBMITTED_ID_STATUSES = {"PENDING", "PENDING_REVIEW", "UNDER_REVIEW", "VERIFIED"}


def account_category(user: dict) -> str:
    """Return the account's category.

    Security: If a user has no explicit `account_category` set, DO NOT fall back
    to STAFF (that would grant admin/back-office access by default). Return the
    restricted GUEST category so the account only reaches public/guest views
    until an administrator explicitly assigns a real category.
    """
    category = str(user.get("account_category") or "").strip().upper()
    return category if category in ACCOUNT_CATEGORIES else GUEST


def workspace_path(user: dict) -> str:
    return {
        STAFF: "/admin",
        PROPERTY_ADVERTISER: "/advertiser",
        GUEST: "/",
    }.get(account_category(user), "/")


async def require_staff(user: dict = Depends(get_current_user)) -> dict:
    if account_category(user) != STAFF or user.get("status", "ACTIVE") not in ACTIVE_ACCOUNT_STATUSES:
        raise HTTPException(403, "An active Staff Account is required")
    return user


async def require_property_writer(user: dict = Depends(get_current_user)) -> dict:
    """Allow staff, or a fully verified Property Advertiser, to write Property data."""
    category = account_category(user)
    if user.get("status", "ACTIVE") not in ACTIVE_ACCOUNT_STATUSES:
        raise HTTPException(403, "Active account required")
    if category == STAFF:
        return user
    if category != PROPERTY_ADVERTISER:
        if category == REFERRAL_PARTNER:
            raise HTTPException(403, "Referral Partner Accounts cannot create or edit Property listings")
        raise HTTPException(403, "A verified Property Advertiser Account is required")

    profile = await db.advertiser_profiles.find_one({
        "user_id": user["id"],
        "status": "VERIFIED",
        "relationship_type": {"$in": sorted(PROPERTY_RELATIONSHIPS)},
    }, {"_id": 0, "id": 1})
    government_id = await db.identity_documents.find_one({
        "user_id": user["id"],
        "document_type": {"$in": sorted(GOVERNMENT_ID_TYPES)},
        "status": "VERIFIED",
    }, {"_id": 0, "id": 1})
    if not profile:
        raise HTTPException(403, "Verified Property Advertiser profile required")
    if not government_id:
        raise HTTPException(403, "One verified government-issued ID is required")
    return user


async def require_property_submitter(user: dict = Depends(get_current_user)) -> dict:
    """Allow an active advertiser to submit once an ID is awaiting review.

    Staff verification remains mandatory for publication, but it must not stop
    a complete property submission from entering the staff review queue.
    """
    if user.get("status", "ACTIVE") not in ACTIVE_ACCOUNT_STATUSES:
        raise HTTPException(403, "Active account required")
    if account_category(user) != PROPERTY_ADVERTISER:
        raise HTTPException(403, "Property Advertiser account required")

    profile = await db.advertiser_profiles.find_one({
        "user_id": user["id"],
        "relationship_type": {"$in": sorted(PROPERTY_RELATIONSHIPS)},
    }, {"_id": 0, "id": 1})
    if not profile:
        raise HTTPException(403, "Complete the Property Advertiser profile before submitting this property")

    government_id = await db.identity_documents.find_one({
        "user_id": user["id"],
        "document_type": {"$in": sorted(GOVERNMENT_ID_TYPES)},
        "status": {"$in": sorted(SUBMITTED_ID_STATUSES)},
    }, {"_id": 0, "id": 1})
    if not government_id:
        raise HTTPException(
            403,
            "Submit one government-issued identity document before submitting this property",
        )
    return user


async def require_referral_partner(user: dict = Depends(get_current_user)) -> dict:
    if account_category(user) != REFERRAL_PARTNER or user.get("status", "ACTIVE") not in ACTIVE_ACCOUNT_STATUSES:
        raise HTTPException(403, "An active Referral Partner Account is required")
    return user
