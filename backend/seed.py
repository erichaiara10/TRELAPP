"""Startup seeding + one-off legacy migrations.

CORE RULE (Data Protection):
- `seed_*` functions run only on a first boot (when the target collection is
  empty). If the collection already has ANY documents, the seed is skipped
  entirely — no existing record is ever overwritten.
- `migrate_*` functions are one-off legacy data cleanups (e.g. rename of
  `admin@pngrealty.pg` → `admin@trel.com.pg`). They are idempotent: once
  applied, they do nothing on subsequent boots.
"""
import logging
import os
from pathlib import Path

from core.db import db, new_id, now_iso
from core.security import hash_password
from models import Property, PropertyType, Requirement
from seed_data import (
    DEFAULT_CONTENT, DEFAULT_LOCATIONS, DEFAULT_PAGE_CONTENT,
    DEFAULT_PROPERTY_TYPES, DEMO_PROPERTIES, LEGACY_EMAIL_MAP,
    LEGACY_PROPERTY_TYPE_NAME_MAP, SAMPLE_REQUIREMENTS,
)

logger = logging.getLogger("trel")


DEMO_USERS = [
    {"email": os.environ.get("ADMIN_EMAIL", "admin@trel.com.pg"), "name": "System Admin", "role": "system_admin"},
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
    admin_pwd = os.environ.get("ADMIN_PASSWORD", "Admin@123")
    for u in DEMO_USERS:
        if await db.users.find_one({"email": u["email"]}, {"_id": 0, "id": 1}):
            continue  # user exists → leave untouched (no password reset)
        pwd = admin_pwd if u["role"] == "system_admin" else "Password@123"
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
    if await db.content.count_documents({}) > 0:
        return
    for k, v in DEFAULT_CONTENT.items():
        await db.content.insert_one({"key": k, "value": v})


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
    admin_pwd = os.environ.get("ADMIN_PASSWORD", "Admin@123")
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@trel.com.pg")
    try:
        creds_dir = Path("/app/memory")
        creds_dir.mkdir(parents=True, exist_ok=True)
        (creds_dir / "test_credentials.md").write_text(f"""# Triumph Real Estate Limited (TREL) — Test Credentials

## Admin
- Email: `{admin_email}`
- Password: `{admin_pwd}`
- Role: system_admin

## Staff (all password: `Password@123`)
- director@trel.com.pg  (managing_director)
- sales@trel.com.pg     (sales_agent)
- leasing@trel.com.pg   (leasing_agent)
- marketing@trel.com.pg (marketing_officer)

Note: Passwords are ONLY seeded on first boot. If an existing admin has
changed their password, it will NOT be reset by the seed script.

## Auth Endpoints
- POST /api/auth/login  {{ email, password }} -> returns token
- POST /api/auth/logout
- GET  /api/auth/me     (Authorization: Bearer <token>)
""")
    except Exception as e:
        logger.warning(f"Could not write test credentials: {e}")


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
