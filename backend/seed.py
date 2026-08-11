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
from models import (
    LocationReference, MarketConfiguration, MasterProperty,
    Property, PropertyType, Requirement,
)
from seed_data import (
    DEFAULT_CONTENT, DEFAULT_LOCATIONS, DEFAULT_MARKET_CONFIG_PARAMS,
    DEFAULT_PAGE_CONTENT, DEFAULT_PROPERTY_TYPES, DEMO_PROPERTIES,
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


# ---------------- Market Intelligence (Phase 1 Data Aggregation) ----------------
def _infer_master_class(property_type: str) -> tuple[str, bool]:
    """Rough class + vacancy inference for backfill only. Human-editable via
    the master-property update endpoint later."""
    pt = (property_type or "").lower()
    is_vacant = "vacant" in pt or "land" in pt or "portion" in pt
    if "commercial" in pt or "industrial" in pt or "warehouse" in pt or "office" in pt or "retail" in pt:
        return "commercial_industrial", is_vacant
    if is_vacant:
        return "vacant_land", True
    return "residential", False


async def migrate_backfill_master_properties():
    """One-off, idempotent: every TREL property that doesn't yet have a
    `master_property_id` gets a 1:1 master property auto-created and linked.
    Runs on every boot; the `$exists: false` filter makes it a no-op once
    every record is already linked."""
    cursor = db.properties.find(
        {"$or": [{"master_property_id": {"$exists": False}}, {"master_property_id": None}]},
        {"_id": 0},
    )
    created = 0
    async for p in cursor:
        cls, is_vacant = _infer_master_class(p.get("property_type") or "")
        land_m2 = None
        if p.get("total_area_ha") is not None:
            try:
                land_m2 = float(p["total_area_ha"]) * 10000.0
            except (TypeError, ValueError):
                land_m2 = None
        master = MasterProperty(
            property_class=cls,
            property_subtype=p.get("property_type"),
            lot_number=p.get("allotment_number"),
            section_number=p.get("section_number"),
            portion_number=p.get("full_portion_number"),
            street=p.get("street_name"),
            suburb=p.get("suburb"),
            city=p.get("location"),
            province=p.get("province"),
            land_area_m2=land_m2,
            trel_property_id=p["id"],
            is_vacant=is_vacant,
            canonical_fields={"provenance": "trel_backfill", "trel_property_id": p["id"]},
        ).model_dump()
        await db.master_properties.insert_one(master)
        await db.properties.update_one(
            {"id": p["id"]},
            {"$set": {"master_property_id": master["id"], "updated_at": now_iso()}},
        )
        created += 1
    if created:
        logger.info(f"Backfill: created {created} master_properties linked to existing properties")


async def seed_market_configuration():
    if await db.market_configuration.count_documents({}) > 0:
        # Backfill: any config missing retention params gets them injected
        # in-place so the Configuration UI renders correct defaults.
        await db.market_configuration.update_many(
            {"parameters.retention": {"$exists": False}},
            {"$set": {"parameters.retention": DEFAULT_MARKET_CONFIG_PARAMS["retention"]}},
        )
        return
    doc = MarketConfiguration(
        version="COMBINED-1.0",
        algorithm="combined",
        active=True,
        parameters=DEFAULT_MARKET_CONFIG_PARAMS,
        notes="Baseline v1.0 — TRELPNG algorithm specs (MATCH-1.0 + GUIDE-1.0).",
    ).model_dump()
    await db.market_configuration.insert_one(doc)


async def seed_location_reference():
    """Bootstraps `location_reference` from the existing province/city/suburb
    hierarchy. Skipped once the collection has any docs."""
    if await db.location_reference.count_documents({}) > 0:
        return
    provinces = await db.provinces.find({}, {"_id": 0}).to_list(500)
    for prov in provinces:
        cities = await db.cities.find({"province_id": prov["id"]}, {"_id": 0}).to_list(500)
        if not cities:
            await db.location_reference.insert_one(
                LocationReference(province=prov["name"]).model_dump()
            )
            continue
        for city in cities:
            suburbs = await db.suburbs.find({"city_id": city["id"]}, {"_id": 0}).to_list(2000)
            if not suburbs:
                await db.location_reference.insert_one(
                    LocationReference(province=prov["name"], city=city["name"]).model_dump()
                )
                continue
            for sub in suburbs:
                await db.location_reference.insert_one(
                    LocationReference(
                        province=prov["name"], city=city["name"], suburb=sub["name"],
                    ).model_dump()
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

    # ---- Market Intelligence indexes (Phase 1) ----
    await db.market_sources.create_index("name", unique=True)
    await db.market_listings.create_index(
        [("source_id", 1), ("source_listing_id", 1)], unique=True
    )
    await db.market_listings.create_index("suburb")
    await db.market_listings.create_index(
        [("lot_number", 1), ("section_number", 1), ("suburb", 1)]
    )
    await db.market_listings.create_index("last_seen")
    await db.market_listing_snapshots.create_index("market_listing_id")
    await db.master_properties.create_index(
        [("lot_number", 1), ("section_number", 1), ("suburb", 1)]
    )
    await db.master_properties.create_index("trel_property_id")
    await db.master_properties.create_index("suburb")
    await db.property_units.create_index("master_property_id")
    await db.property_matches.create_index("market_listing_id")
    await db.property_matches.create_index("master_property_id")
    await db.property_matches.create_index([("status", 1), ("created_at", -1)])
    await db.market_review_cases.create_index([("status", 1), ("created_at", -1)])
    await db.market_audit_events.create_index([("created_at", -1)])
    await db.market_audit_events.create_index([("entity_type", 1), ("entity_id", 1)])
    await db.market_configuration.create_index(
        [("version", 1), ("algorithm", 1)], unique=True
    )
    await db.market_configuration.create_index([("algorithm", 1), ("active", 1)])
    await db.location_reference.create_index(
        [("province", 1), ("city", 1), ("suburb", 1), ("local_area", 1), ("street", 1)]
    )
    await db.collection_runs.create_index([("source_id", 1), ("started_at", -1)])
    await db.valuation_requests.create_index("created_at")
    await db.guidance_results.create_index("valuation_request_id")
    await db.guidance_comparables.create_index("guidance_result_id")

    # ---- Legacy migrations (one-off, idempotent) ----
    await migrate_legacy_user_emails()
    await migrate_land_category()

    # ---- First-boot seeds (skip if collection has data) ----
    await seed_users()
    await seed_properties()
    await seed_content()
    await seed_page_content()
    await seed_requirements()
    await seed_locations()
    await seed_property_types()
    await seed_market_configuration()
    await seed_location_reference()

    # ---- Market Intelligence backfill (idempotent — only affects new/unlinked properties) ----
    await migrate_backfill_master_properties()

    write_test_credentials()
    logger.info("Startup complete — seeds are first-boot only; existing data preserved")
