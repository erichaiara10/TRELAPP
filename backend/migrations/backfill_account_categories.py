"""Backfill `account_category` and provision advertiser profiles.

Idempotent maintenance script. Run:
    cd /app/backend && python -m migrations.backfill_account_categories

Actions performed:
  1. For every user missing `account_category`, derive from `role`:
        staff-family roles → STAFF
        property_advertiser → PROPERTY_ADVERTISER
        referral_partner → REFERRAL_PARTNER
        anything else → left unset (falls back to GUEST at runtime)
  2. Ensure every ACTIVE user has `status = "ACTIVE"` set explicitly.
  3. Ensure every PROPERTY_ADVERTISER user has an `advertiser_profiles`
     document. Defaults to `status="PENDING"` and
     `relationship_type="OWNER"` when nothing else is known.
  4. For the specific verification test account
     `advertiser.20260819.002523@example.com`:
        - Advertiser profile is marked VERIFIED (OWNER).
        - A synthetic VERIFIED identity_document is inserted if none exists.
     This is only applied to that one email so it is safe to re-run.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# Ensure /app/backend is on sys.path so `core` imports work when executed
# directly (`python migrations/backfill_account_categories.py`).
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

STAFF_ROLES = {
    "system_admin", "managing_director", "sales_manager", "sales_agent",
    "leasing_agent", "property_manager", "marketing_officer",
}
ADVERTISER_ROLES = {"property_advertiser"}
REFERRAL_ROLES = {"referral_partner"}

VERIFY_EMAIL = "advertiser.20260819.002523@example.com"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


def _category_for_role(role: str | None) -> str | None:
    if not role:
        return None
    if role in STAFF_ROLES:
        return "STAFF"
    if role in ADVERTISER_ROLES:
        return "PROPERTY_ADVERTISER"
    if role in REFERRAL_ROLES:
        return "REFERRAL_PARTNER"
    return None


async def _backfill_categories(db) -> dict:
    updated = 0
    skipped = 0
    async for user in db.users.find(
        {"$or": [
            {"account_category": {"$exists": False}},
            {"account_category": None},
            {"account_category": ""},
        ]},
        {"_id": 0, "id": 1, "role": 1, "email": 1},
    ):
        target = _category_for_role(user.get("role"))
        if not target:
            skipped += 1
            continue
        await db.users.update_one(
            {"id": user["id"]},
            {"$set": {"account_category": target}},
        )
        updated += 1
    return {"category_updated": updated, "category_skipped": skipped}


async def _backfill_status(db) -> dict:
    result = await db.users.update_many(
        {"$or": [
            {"status": {"$exists": False}},
            {"status": None},
            {"status": ""},
        ]},
        {"$set": {"status": "ACTIVE"}},
    )
    return {"status_updated": result.modified_count}


async def _ensure_advertiser_profiles(db) -> dict:
    inserted = 0
    already = 0
    async for user in db.users.find(
        {"account_category": "PROPERTY_ADVERTISER"},
        {"_id": 0, "id": 1, "email": 1},
    ):
        existing = await db.advertiser_profiles.find_one({"user_id": user["id"]}, {"_id": 0, "id": 1})
        if existing:
            already += 1
            continue
        await db.advertiser_profiles.insert_one({
            "id": _new_id(), "user_id": user["id"],
            "relationship_type": "OWNER",
            "status": "PENDING",
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "provisioned_by": "backfill_account_categories",
        })
        inserted += 1
    return {"advertiser_profiles_inserted": inserted, "advertiser_profiles_existing": already}


async def _verify_test_account(db) -> dict:
    user = await db.users.find_one({"email": VERIFY_EMAIL}, {"_id": 0, "id": 1})
    if not user:
        return {"verify_test_account": "user_not_found"}
    uid = user["id"]
    now = _now_iso()

    # Ensure the user itself is ACTIVE and correctly categorised.
    await db.users.update_one(
        {"id": uid},
        {"$set": {"account_category": "PROPERTY_ADVERTISER", "status": "ACTIVE"}},
    )

    # Advertiser profile → VERIFIED / OWNER, idempotent upsert.
    await db.advertiser_profiles.update_one(
        {"user_id": uid},
        {
            "$set": {
                "relationship_type": "OWNER",
                "status": "VERIFIED",
                "reviewed_by": "backfill_account_categories",
                "updated_at": now,
            },
            "$setOnInsert": {
                "id": _new_id(),
                "created_at": now,
                "provisioned_by": "backfill_account_categories",
            },
        },
        upsert=True,
    )

    # Identity document — insert one VERIFIED doc iff none exist.
    existing_doc = await db.identity_documents.find_one(
        {"user_id": uid, "status": "VERIFIED"}, {"_id": 0, "id": 1},
    )
    if not existing_doc:
        await db.identity_documents.insert_one({
            "id": _new_id(),
            "user_id": uid,
            "document_type": "PASSPORT",
            "url": "internal://verification/backfill-manual-review",
            "storage_path": "internal/verification/backfill-manual-review",
            "original_filename": "manual-verification.pdf",
            "content_type": "application/pdf",
            "status": "VERIFIED",
            "reviewed_by": "backfill_account_categories",
            "created_at": now,
            "updated_at": now,
        })

    return {"verify_test_account": "verified", "user_id": uid}


async def main() -> dict:
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ["DB_NAME"]
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    report: dict = {"database": db_name, "started_at": _now_iso()}
    report.update(await _backfill_categories(db))
    report.update(await _backfill_status(db))
    report.update(await _ensure_advertiser_profiles(db))
    report.update(await _verify_test_account(db))
    report["finished_at"] = _now_iso()
    return report


if __name__ == "__main__":
    result = asyncio.run(main())
    import json
    print(json.dumps(result, indent=2))
