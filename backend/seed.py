"""Startup seeding + one-off migrations.

All functions are idempotent and safe to run on every boot.
"""
import logging
import os
from pathlib import Path

from core.db import db, new_id, now_iso
from core.security import hash_password, verify_password
from models import Property, PropertyType, Requirement
from seed_data import (
    DEFAULT_CONTENT, DEFAULT_LOCATIONS, DEFAULT_PAGE_CONTENT,
    DEFAULT_PROPERTY_TYPES, DEMO_PROPERTIES, LEGACY_AGENCY_NAMES,
    LEGACY_EMAIL_MAP, LEGACY_PROPERTY_TYPE_NAME_MAP, SAMPLE_REQUIREMENTS,
)

logger = logging.getLogger("trel")


DEMO_USERS = [
    {"email": os.environ.get("ADMIN_EMAIL", "admin@trel.com.pg"), "name": "System Admin", "role": "system_admin"},
    {"email": "director@trel.com.pg", "name": "Naomi Kila", "role": "managing_director"},
    {"email": "sales@trel.com.pg", "name": "John Namaliu", "role": "sales_agent"},
    {"email": "leasing@trel.com.pg", "name": "Grace Toua", "role": "leasing_agent"},
    {"email": "marketing@trel.com.pg", "name": "Peter Amet", "role": "marketing_officer"},
]


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


async def seed_users():
    admin_pwd = os.environ.get("ADMIN_PASSWORD", "Admin@123")
    for u in DEMO_USERS:
        exists = await db.users.find_one({"email": u["email"]})
        pwd = admin_pwd if u["role"] == "system_admin" else "Password@123"
        if not exists:
            await db.users.insert_one({
                "id": new_id(), "email": u["email"], "name": u["name"],
                "role": u["role"], "phone": None,
                "password_hash": hash_password(pwd), "created_at": now_iso(),
            })
        elif not verify_password(pwd, exists.get("password_hash", "")):
            await db.users.update_one({"email": u["email"]},
                                      {"$set": {"password_hash": hash_password(pwd)}})


async def seed_properties():
    if await db.properties.count_documents({}) == 0:
        for p in DEMO_PROPERTIES:
            await db.properties.insert_one(Property(**p).model_dump())


async def seed_content():
    for k, v in DEFAULT_CONTENT.items():
        await db.content.update_one({"key": k},
                                    {"$setOnInsert": {"key": k, "value": v}}, upsert=True)
    site = await db.content.find_one({"key": "site"}, {"_id": 0})
    current_name = (site or {}).get("value", {}).get("agency_name", "")
    needs_full_reset = (not current_name) or (current_name in LEGACY_AGENCY_NAMES) or ("PNG Realty" in current_name)
    if site and needs_full_reset:
        await db.content.update_one({"key": "site"},
                                    {"$set": {"value": DEFAULT_CONTENT["site"]}})
    else:
        current_logo = (site or {}).get("value", {}).get("logo_url", "")
        if "TREL%20Letter%20Head" in current_logo or "TREL Letter Head" in current_logo:
            await db.content.update_one({"key": "site"},
                                        {"$set": {"value.logo_url": DEFAULT_CONTENT["site"]["logo_url"]}})
        cur_val = (site or {}).get("value", {}) if site else {}
        backfill = {}
        for k in ("favicon_url", "og_image_url", "og_description"):
            if not cur_val.get(k):
                backfill[f"value.{k}"] = DEFAULT_CONTENT["site"][k]
        if backfill:
            await db.content.update_one({"key": "site"}, {"$set": backfill})
    about = await db.content.find_one({"key": "about"}, {"_id": 0})
    if about and about.get("value", {}).get("heading", "").endswith("PNG Realty"):
        await db.content.update_one({"key": "about"}, {"$set": {"value": DEFAULT_CONTENT["about"]}})
    why = await db.content.find_one({"key": "why"}, {"_id": 0})
    if why and why.get("value", {}).get("heading") == "Why choose us":
        await db.content.update_one({"key": "why"}, {"$set": {"value": DEFAULT_CONTENT["why"]}})


async def seed_requirements():
    if await db.requirements.count_documents({}) == 0:
        for s in SAMPLE_REQUIREMENTS:
            await db.requirements.insert_one(Requirement(**s).model_dump())


async def seed_page_content():
    for page, defaults in DEFAULT_PAGE_CONTENT.items():
        await db.page_content.update_one(
            {"page": page},
            {"$setOnInsert": {"page": page, "sections": defaults,
                              "updated_at": now_iso(), "updated_by": None}},
            upsert=True,
        )
    sell = await db.page_content.find_one({"page": "sell"}, {"_id": 0}) or {}
    sell_benefits = (sell.get("sections") or {}).get("benefits") or []
    if any((b or {}).get("title", "").lower().startswith("free appraisal") for b in sell_benefits):
        await db.page_content.update_one(
            {"page": "sell"},
            {"$set": {"sections.benefits": DEFAULT_PAGE_CONTENT["sell"]["benefits"],
                      "sections.hero.intro": DEFAULT_PAGE_CONTENT["sell"]["hero"]["intro"],
                      "updated_at": now_iso()}},
        )


async def seed_locations():
    for entry in DEFAULT_LOCATIONS:
        pname = entry["province"]
        pdoc = await db.provinces.find_one({"name": pname})
        if not pdoc:
            pid = new_id()
            await db.provinces.insert_one({"id": pid, "name": pname,
                                           "created_at": now_iso()})
        else:
            pid = pdoc["id"]
        for cname, suburbs in (entry.get("cities") or {}).items():
            cdoc = await db.cities.find_one({"name": cname, "province_id": pid})
            if not cdoc:
                cid = new_id()
                await db.cities.insert_one({"id": cid, "name": cname,
                                            "province_id": pid, "created_at": now_iso()})
            else:
                cid = cdoc["id"]
            for sname in suburbs:
                if not await db.suburbs.find_one({"name": sname, "city_id": cid}):
                    await db.suburbs.insert_one({
                        "id": new_id(), "name": sname, "city_id": cid,
                        "province_id": pid, "source": "admin", "created_at": now_iso(),
                    })
    # Backfill province on existing properties by city→province mapping
    async for prop in db.properties.find(
        {"$or": [{"province": None}, {"province": {"$exists": False}}, {"province": ""}]},
        {"_id": 0, "id": 1, "location": 1},
    ):
        loc = (prop.get("location") or "").strip()
        if not loc:
            continue
        c = await db.cities.find_one({"name": loc})
        if not c:
            continue
        p = await db.provinces.find_one({"id": c["province_id"]})
        if p:
            await db.properties.update_one(
                {"id": prop["id"]},
                {"$set": {"province": p["name"], "updated_at": now_iso()}},
            )


async def seed_property_types_and_migrate():
    """Seed the 6 default property types (idempotent) and backfill existing
    properties: convert land_category -> new property_type + wipe the field."""
    await db.property_types.create_index("name", unique=True)
    for name, scheme, order in DEFAULT_PROPERTY_TYPES:
        await db.property_types.update_one(
            {"name": name},
            {"$setOnInsert": PropertyType(name=name, legal_scheme=scheme, order=order).model_dump()},
            upsert=True,
        )
    async for p in db.properties.find({}, {"_id": 0, "id": 1, "property_type": 1, "land_category": 1}):
        updates = {}
        pt = (p.get("property_type") or "").strip()
        lc = (p.get("land_category") or "").strip()
        if lc == "large_portion":
            updates["property_type"] = "Large Land – Portion / Customary"
        elif pt.lower() in LEGACY_PROPERTY_TYPE_NAME_MAP:
            updates["property_type"] = LEGACY_PROPERTY_TYPE_NAME_MAP[pt.lower()]
        if updates or "land_category" in p:
            unset = {"land_category": ""} if "land_category" in p else None
            spec = {"$set": {**updates, "updated_at": now_iso()}} if updates else {}
            if unset:
                spec["$unset"] = unset
            if spec:
                await db.properties.update_one({"id": p["id"]}, spec)


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

## Auth Endpoints
- POST /api/auth/login  {{ email, password }} -> returns token
- POST /api/auth/logout
- GET  /api/auth/me     (Authorization: Bearer <token>)
""")
    except Exception as e:
        logger.warning(f"Could not write test credentials: {e}")


async def run_startup():
    await db.users.create_index("email", unique=True)
    await db.page_content.create_index("page", unique=True)
    await db.provinces.create_index("name", unique=True)
    await db.cities.create_index([("name", 1), ("province_id", 1)], unique=True)
    await db.suburbs.create_index([("name", 1), ("city_id", 1)], unique=True)
    await migrate_legacy_user_emails()
    await seed_users()
    await seed_properties()
    await seed_content()
    await seed_page_content()
    await seed_requirements()
    await seed_locations()
    await seed_property_types_and_migrate()
    write_test_credentials()
    logger.info("Startup seeding complete")
