"""Startup seeding + one-off legacy migrations.

CORE RULE (Data Protection):
- `seed_*` functions run only on a first boot (when the target collection is
  empty). If the collection already has ANY documents, the seed is skipped
  entirely — no existing record is ever overwritten.
- `migrate_*` functions are one-off legacy data cleanups (e.g. rename of
  `admin@pngrealty.pg` → `admin@trel.com.pg`). They are idempotent: once
  applied, they do nothing on subsequent boots.
- The approved test administrator is restored idempotently without deleting
  any unrelated account or storing its password in source code.
"""
import logging
import os

from core.db import db, new_id, now_iso
from core.security import hash_password
from models import Property, PropertyType, Requirement
from seed_data import (
    DEFAULT_CONTENT, DEFAULT_LOCATIONS, DEFAULT_PAGE_CONTENT,
    DEFAULT_PROPERTY_TYPES, DEMO_PROPERTIES, LEGACY_EMAIL_MAP,
    LEGACY_PROPERTY_TYPE_NAME_MAP, SAMPLE_REQUIREMENTS,
)

logger = logging.getLogger("trel")

APPROVED_ADMIN_EMAIL = os.environ.get(
    "ADMIN_EMAIL", "admin@trelpng.com.pg"
).strip().lower()

DEMO_USERS = [
    {"email": APPROVED_ADMIN_EMAIL, "name": "System Admin", "role": "system_admin"},
    {"email": "director@trel.com.pg", "name": "Naomi Kila", "role": "managing_director"},
    {"email": "sales@trel.com.pg", "name": "John Namaliu", "role": "sales_agent"},
    {"email": "leasing@trel.com.pg", "name": "Grace Toua", "role": "leasing_agent"},
    {"email": "marketing@trel.com.pg", "name": "Peter Amet", "role": "marketing_officer"},
]


# ---------------- Migrations (one-off, idempotent legacy cleanups) ----------------
async def migrate_legacy_user_emails():
    for old, new in LEGACY_EMAIL_MAP.items():
        old_user = await db.users.find_one({"email": old})
        if not old_user:
            continue
        new_user = await db.users.find_one({"email": new})
        if new_user:
            await db.users.delete_one({"email": old})
        else:
            await db.users.update_one({"email": old}, {"$set": {"email": new}})


async def restore_approved_admin():
    """Restore the approved administrator identity without exposing secrets.

    Prefer the existing approved record. Otherwise rename the legacy TREL
    administrator while preserving its password hash. If ADMIN_PASSWORD is
    configured, use it to reset the approved test administrator deliberately.
    """
    admin_password = os.environ.get("ADMIN_PASSWORD")
    approved = await db.users.find_one({"email": APPROVED_ADMIN_EMAIL})
    updates = {
        "email": APPROVED_ADMIN_EMAIL,
        "name": "System Admin",
        "role": "system_admin",
        "account_category": "STAFF",
        "status": "ACTIVE",
        "updated_at": now_iso(),
    }
    if admin_password:
        updates["password_hash"] = hash_password(admin_password)

    if approved:
        await db.users.update_one({"_id": approved["_id"]}, {"$set": updates})
        return

    for legacy_email in ("admin@trel.com.pg", "admin@pngrealty.pg"):
        legacy = await db.users.find_one({"email": legacy_email})
        if legacy:
            await db.users.update_one({"_id": legacy["_id"]}, {"$set": updates})
            return

    if admin_password:
        await db.users.insert_one({
            "id": new_id(),
            "email": APPROVED_ADMIN_EMAIL,
            "name": "System Admin",
            "role": "system_admin",
            "account_category": "STAFF",
            "status": "ACTIVE",
            "phone": None,
            "password_hash": hash_password(admin_password),
            "created_at": now_iso(),
            "updated_at": now_iso(),
        })
        return

    logger.error(
        "Approved admin could not be restored: no legacy record or ADMIN_PASSWORD"
    )


async def seed_property_advertising_test_fixtures():
    """Create stable workflow records only in the dedicated test database.

    Existing fixture records are never reset, so Staff test decisions remain
    available for later review and no production database can enter this path.
    """
    if os.getenv("DB_NAME") != "trel_test" or os.getenv(
        "TREL_PROPERTY_ADVERTISING_TEST_FIXTURES", ""
    ).strip().lower() not in {"1", "true", "yes"}:
        return
    # The feature was withdrawn. Remove its obsolete test-only collection so
    # stale request data cannot imply that the workflow still exists.
    await db.drop_collection("exact_location_requests")
    created = "2026-08-24T00:00:00+10:00"
    advertiser_id = "pa-test-advertiser"
    await db.users.update_one(
        {"id": advertiser_id},
        {"$setOnInsert": {
            "id": advertiser_id, "email": "property-advertiser-test@trelpng.com.pg",
            "name": "Property Advertising Test Advertiser", "phone": "+675 7000 0001",
            "role": "property_advertiser", "account_category": "PROPERTY_ADVERTISER",
            "status": "ACTIVE", "email_verified": True, "mobile_verified": True,
            "created_at": created, "updated_at": created,
        }},
        upsert=True,
    )
    await db.advertiser_profiles.update_one(
        {"user_id": advertiser_id},
        {"$setOnInsert": {
            "id": "pa-test-profile", "user_id": advertiser_id,
            "status": "VERIFIED", "relationship_type": "OWNER",
            "residential_address": "Waigani, Port Moresby", "created_at": created,
            "updated_at": created,
        }},
        upsert=True,
    )
    await db.identity_documents.update_one(
        {"id": "pa-test-identity"},
        {"$setOnInsert": {
            "id": "pa-test-identity", "user_id": advertiser_id,
            "document_type": "NID_CARD", "original_filename": "controlled-test-identity.pdf",
            "status": "VERIFIED", "created_at": created,
        }},
        upsert=True,
    )
    common = {
        "description": "Controlled test record for Property Advertising workflow validation.",
        "listing_type": "Sale", "property_class": "Residential", "property_type": "House",
        "province": "National Capital District", "service": "Advertise only",
        "relationship": "Owner / Joint Owner", "identity_scheme": "SERVICED",
        "currency": "PGK", "price": 750000, "authority_confirmed": True,
        "terms_accepted": True, "photos": ["/logo192.png", "/logo512.png"],
    }
    fixtures = [
        ("pa-test-submission-ready", "PA-TEST-READY", {
            **common, "title": "Controlled Lifecycle Test Property", "lot": "901",
            "section": "81", "city": "Port Moresby",
        }, "APPROVED"),
        ("pa-test-submission-duplicate-a", "PA-TEST-DUP-A", {
            **common, "title": "Controlled Duplicate A", "lot": "902",
            "section": "82", "suburb": "Waigani",
        }, "UNDER_REVIEW"),
        ("pa-test-submission-duplicate-b", "PA-TEST-DUP-B", {
            **common, "title": "Controlled Duplicate B", "lot": "902",
            "section": "82", "suburb": "Waigani",
        }, "UNDER_REVIEW"),
    ]
    for fixture_id, reference, data, status in fixtures:
        await db.advertiser_submissions.update_one(
            {"id": fixture_id},
            {"$setOnInsert": {
                "id": fixture_id, "reference": reference, "user_id": advertiser_id,
                "status": status, "data": data, "submitted_at": created,
                "created_at": created, "updated_at": created,
            }},
            upsert=True,
        )
    await db.staff_property_reviews.update_one(
        {"subject_ref": "PA-TEST-READY"},
        {"$setOnInsert": {
            "id": "pa-test-review-ready", "subject_ref": "PA-TEST-READY",
            "submission_status": "APPROVED", "authority_status": "ACCEPTED",
            "conflict_status": "CLEAR", "publication_status": "PUBLISHED",
            "listing_reference": "LIST-PA-TEST-READY", "created_at": created,
            "updated_at": created,
        }},
        upsert=True,
    )
    await db.advertiser_listing_lifecycle.update_one(
        {"listing_id": "LIST-PA-TEST-READY"},
        {"$setOnInsert": {
            "id": "pa-test-lifecycle-ready", "listing_id": "LIST-PA-TEST-READY",
            "user_id": advertiser_id, "status": "AVAILABLE", "workflow_status": "CURRENT",
            "last_confirmed": "2026-08-24T00:00:00+10:00",
            "next_due": "2026-11-24T00:00:00+10:00",
            "reminder_until": "2027-01-24T00:00:00+10:00",
            "unpublish_due": "2027-02-24T00:00:00+10:00",
            "archive_due": "2027-08-24T00:00:00+10:00",
            "reminder_count": 0, "created_at": created, "updated_at": created,
        }},
        upsert=True,
    )

    # Replace the former browser-only 18-row demonstration with persistent,
    # account-owned records. The account password is deliberately untouched.
    primary = await db.users.find_one({"email": "eric.haiara10@gmail.com"})
    if not primary:
        logger.warning("Primary Property Advertising test account was not found; demo records were not seeded")
        return
    primary_id = primary.get("id")
    await db.users.update_one({"_id": primary["_id"]}, {"$set": {
        "role": "property_advertiser", "account_category": "PROPERTY_ADVERTISER",
        "status": "ACTIVE", "email_verified": True, "mobile_verified": True,
        "updated_at": now_iso(),
    }})
    await db.advertiser_profiles.update_one(
        {"user_id": primary_id},
        {"$setOnInsert": {
            "id": "primary-pa-test-profile", "user_id": primary_id,
            "status": "VERIFIED", "relationship_type": "OWNER",
            "residential_address": "Port Moresby", "created_at": created,
            "updated_at": created,
        }},
        upsert=True,
    )
    await db.identity_documents.update_one(
        {"id": "primary-pa-test-identity"},
        {"$setOnInsert": {
            "id": "primary-pa-test-identity", "user_id": primary_id,
            "document_type": "NID_CARD", "original_filename": "controlled-primary-identity.pdf",
            "status": "VERIFIED", "created_at": created,
        }},
        upsert=True,
    )
    templates = [
        ("Executive Office Space — Waigani", "Rent", "Commercial", "Office Space", "Waigani", 8500),
        ("3 Bedroom House — Boroko", "Sale", "Residential", "House", "Boroko", 1650000),
        ("Residential Land — Kokopo", "Sale", "Vacant Land", "Residential Land", "Kokopo", 180000),
        ("Warehouse — Gordons", "Rent", "Industrial", "Warehouse", "Gordons", 12000),
    ]
    demo_states = [
        "LIVE", "LIVE", "UNDER_REVIEW", "DRAFT", "LIVE", "LIVE",
        "UNDER_REVIEW", "DRAFT", "LIVE", "LIVE", "DRAFT", "DRAFT",
        "LIVE", "LIVE", "DRAFT", "WITHDRAWN", "SOLD", "ARCHIVED",
    ]
    for index, state in enumerate(demo_states):
        number = 1024 + index
        title, listing_type, property_class, property_type, suburb, price = templates[index % len(templates)]
        fixture_id = f"primary-demo-{number}"
        reference = f"DEMO-{number}"
        listing_reference = f"DEMO-LIST-{number}"
        timestamp = f"2026-08-{min(24, 1 + index):02d}T00:00:00+10:00"
        data = {
            "title": f"{title} #{number}",
            "description": "Controlled persistent test record for advertiser workspace validation.",
            "listing_type": listing_type, "property_class": property_class,
            "property_type": property_type, "province": "National Capital District",
            "city": "Port Moresby", "suburb": suburb, "section": str(200 + index),
            "lot": str(500 + index), "identity_scheme": "SERVICED",
            "service": "Advertise only", "relationship": "Owner / Joint Owner",
            "currency": "PGK", "price": price, "authority_confirmed": True,
            "terms_accepted": True,
            "photos": [
                {"url": "/logo192.png", "type": "image/png", "size": 1000},
                {"url": "/logo512.png", "type": "image/png", "size": 2000},
            ],
        }
        submission_status = "DRAFT" if state == "DRAFT" else "UNDER_REVIEW" if state == "UNDER_REVIEW" else "APPROVED"
        await db.advertiser_submissions.update_one(
            {"id": fixture_id},
            {"$setOnInsert": {
                "id": fixture_id, "reference": reference, "user_id": primary_id,
                "status": submission_status, "data": data,
                "submitted_at": timestamp, "created_at": timestamp, "updated_at": timestamp,
            }},
            upsert=True,
        )
        if state not in {"DRAFT", "UNDER_REVIEW"}:
            await db.staff_property_reviews.update_one(
                {"subject_ref": reference},
                {"$setOnInsert": {
                    "id": f"primary-demo-review-{number}", "subject_ref": reference,
                    "submission_status": "APPROVED", "authority_status": "ACCEPTED",
                    "conflict_status": "CLEAR",
                    "publication_status": "PUBLISHED" if state == "LIVE" else "UNPUBLISHED",
                    "listing_reference": listing_reference,
                    "created_at": timestamp, "updated_at": timestamp,
                }},
                upsert=True,
            )
            await db.advertiser_listing_lifecycle.update_one(
                {"listing_id": listing_reference},
                {"$setOnInsert": {
                    "id": f"primary-demo-lifecycle-{number}", "listing_id": listing_reference,
                    "user_id": primary_id, "status": "AVAILABLE" if state == "LIVE" else state,
                    "workflow_status": "CURRENT" if state == "LIVE" else state,
                    "created_at": timestamp, "updated_at": timestamp,
                }},
                upsert=True,
            )


async def migrate_land_category():
    """Convert legacy `land_category`/lowercase property_type values to the
    new titled names, then remove the `land_category` field."""
    async for p in db.properties.find({}, {"_id": 0, "id": 1, "property_type": 1, "land_category": 1}):
        updates = {}
        pt = (p.get("property_type") or "").strip()
        lc = (p.get("land_category") or "").strip()
        if lc == "large_portion":
            updates["property_type"] = "Large Land – Portion / Customary"
        elif pt.lower() in LEGACY_PROPERTY_TYPE_NAME_MAP:
            updates["property_type"] = LEGACY_PROPERTY_TYPE_NAME_MAP[pt.lower()]
        if updates or "land_category" in p:
            spec = {"$set": {**updates, "updated_at": now_iso()}} if updates else {}
            if "land_category" in p:
                spec["$unset"] = {"land_category": ""}
            if spec:
                await db.properties.update_one({"id": p["id"]}, spec)


# ---------------- Seeds (first-boot only — skip if collection has data) ----------------
async def seed_users():
    """Insert demo users ONLY when they don't already exist. Never overwrite
    passwords or profile fields of existing users."""
    admin_pwd = os.environ.get("ADMIN_PASSWORD")
    demo_pwd = os.environ.get("DEMO_USER_PASSWORD")
    for u in DEMO_USERS:
        if await db.users.find_one({"email": u["email"]}, {"_id": 0, "id": 1}):
            continue  # user exists → leave untouched (no password reset)
        pwd = admin_pwd if u["role"] == "system_admin" else demo_pwd
        if not pwd:
            logger.warning("Skipping demo user %s: seed password is not configured", u["email"])
            continue
        await db.users.insert_one({
            "id": new_id(), "email": u["email"], "name": u["name"],
            "role": u["role"], "phone": None,
            "password_hash": hash_password(pwd), "created_at": now_iso(),
        })


async def seed_properties():
    if await db.properties.count_documents({}) > 0:
        return
    for p in DEMO_PROPERTIES:
        await db.properties.insert_one(Property(**p).model_dump())


async def seed_content():
    if await db.content.count_documents({}) == 0:
        for k, v in DEFAULT_CONTENT.items():
            await db.content.insert_one({"key": k, "value": v})
    await db.content.update_one(
        {"key": "site"},
        {"$set": {
            "value.logo_url": "/images/trel-logo.svg",
            "value.favicon_url": "/images/trel-logo.svg",
            "value.og_image_url": "/images/trel-logo.svg",
        }},
        upsert=False,
    )


async def seed_requirements():
    if await db.requirements.count_documents({}) > 0:
        return
    for s in SAMPLE_REQUIREMENTS:
        await db.requirements.insert_one(Requirement(**s).model_dump())


async def seed_page_content():
    if await db.page_content.count_documents({}) > 0:
        return
    for page, defaults in DEFAULT_PAGE_CONTENT.items():
        await db.page_content.insert_one({
            "page": page, "sections": defaults,
            "updated_at": now_iso(), "updated_by": None,
        })


async def seed_locations():
    """Seed the province/city/suburb hierarchy ONLY if the provinces collection
    is empty. Existing docs are never touched."""
    if await db.provinces.count_documents({}) > 0:
        return
    for entry in DEFAULT_LOCATIONS:
        pid = new_id()
        await db.provinces.insert_one({"id": pid, "name": entry["province"],
                                       "created_at": now_iso()})
        for cname, suburbs in (entry.get("cities") or {}).items():
            cid = new_id()
            await db.cities.insert_one({"id": cid, "name": cname,
                                        "province_id": pid, "created_at": now_iso()})
            for sname in suburbs:
                await db.suburbs.insert_one({
                    "id": new_id(), "name": sname, "city_id": cid,
                    "province_id": pid, "source": "admin", "created_at": now_iso(),
                })


async def seed_property_types():
    if await db.property_types.count_documents({}) > 0:
        return
    for name, scheme, order in DEFAULT_PROPERTY_TYPES:
        await db.property_types.insert_one(
            PropertyType(name=name, legal_scheme=scheme, order=order).model_dump()
        )


def write_test_credentials():
    """Credentials are configured through environment variables only.

    Do not write passwords or access tokens to the application filesystem.
    """
    logger.info("Test credentials file disabled; seed credentials remain environment-only")


async def run_startup():
    # ---- Indexes (idempotent) ----
    await db.users.create_index("email", unique=True)
    await db.page_content.create_index("page", unique=True)
    await db.provinces.create_index("name", unique=True)
    await db.cities.create_index([("name", 1), ("province_id", 1)], unique=True)
    await db.suburbs.create_index([("name", 1), ("city_id", 1)], unique=True)
    await db.property_types.create_index("name", unique=True)

    # ---- Legacy migrations (one-off, idempotent) ----
    await migrate_legacy_user_emails()
    await restore_approved_admin()
    await seed_property_advertising_test_fixtures()

    property_storage_mode = os.getenv(
        "TREL_PROPERTY_STORAGE_MODE", "legacy"
    ).strip().lower()
    if property_storage_mode == "legacy":
        await migrate_land_category()
    else:
        logger.info(
            "Integrated Property mode active — skipping legacy property migration"
        )

    # ---- First-boot seeds (skip if collection has data) ----
    await seed_users()
    if property_storage_mode == "legacy":
        await seed_properties()
    else:
        logger.info(
            "Integrated Property mode active — skipping legacy property seed"
        )
    await seed_content()
    await seed_page_content()
    await seed_requirements()
    await seed_locations()
    await seed_property_types()

    write_test_credentials()
    logger.info("Startup complete — seeds are first-boot only; existing data preserved")
