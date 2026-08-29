import asyncio
from datetime import datetime

from pymongo import ReturnDocument

from core.db import DB_NAME, client, db, new_id, now_iso

PROPERTY_ID = "a4de4cc0-5f50-50c8-9f4b-ff75aadb5ec5"
EXPECTED_TITLE = "TEST_IT24_legal_lp"
ADVERTISER_EMAIL = "pai.erebo@unitygroup.com.pg"
IMAGE_URL = (
    "https://images.unsplash.com/photo-1500382017468-9049fed747ef"
    "?auto=format&fit=crop&w=1600&q=80"
)
SERVICE = "Advertise only"


async def main():
    if DB_NAME != "trel_test":
        raise RuntimeError(f"Refusing to repair non-test database: {DB_NAME}")

    master = await db.master_properties.find_one({"id": PROPERTY_ID}, {"_id": 0})
    if not master or master.get("title") != EXPECTED_TITLE:
        raise RuntimeError("Exact TEST_IT24 property guard failed")
    if master.get("source_system") != "TREL_LEGACY":
        raise RuntimeError("Repair is restricted to the expected legacy test record")

    listing = await db.listings.find_one(
        {"property_id": PROPERTY_ID, "responsible_channel_active": True},
        {"_id": 0},
    ) or await db.listings.find_one({"property_id": PROPERTY_ID}, {"_id": 0})
    if not listing or listing.get("title") != EXPECTED_TITLE:
        raise RuntimeError("Expected TEST_IT24 listing was not found")

    property_type = await db.property_types.find_one(
        {"id": master.get("property_type_id")}, {"_id": 0}
    )
    if not property_type or property_type.get("legal_scheme") != "lot_section_street":
        raise RuntimeError("Expected urban lot/section property scheme was not found")

    advertiser = await db.users.find_one(
        {"email": {"$regex": f"^{ADVERTISER_EMAIL}$", "$options": "i"}},
        {"_id": 0},
    )
    if not advertiser or advertiser.get("account_category") != "PROPERTY_ADVERTISER":
        raise RuntimeError("Approved test advertiser was not found")
    if advertiser.get("status") != "ACTIVE" or not advertiser.get("phone"):
        raise RuntimeError("Test advertiser must be active and have a call number")

    identity = await db.identity_documents.find_one(
        {"user_id": advertiser["id"], "status": "VERIFIED"}, {"_id": 0, "id": 1}
    )
    if not identity:
        raise RuntimeError("Test advertiser does not have a verified identity document")

    timestamp = now_iso()
    owner_name = advertiser.get("name") or "Test Property Advertiser"
    owner_norm = owner_name.strip().upper()
    owner_email = advertiser.get("email")
    owner_phone = advertiser.get("phone")

    async with await client.start_session() as session:
        async with session.start_transaction():
            party = await db.parties.find_one(
                {"normalized_name": owner_norm, "email_norm": owner_email.upper()},
                {"_id": 0},
                session=session,
            )
            if not party:
                party = {
                    "id": new_id(),
                    "party_type": "PERSON",
                    "display_name": owner_name,
                    "normalized_name": owner_norm,
                    "email": owner_email,
                    "email_norm": owner_email.upper(),
                    "phone": owner_phone,
                    "phone_norm": owner_phone.upper(),
                    "created_at": timestamp,
                    "updated_at": timestamp,
                }
                await db.parties.insert_one(party, session=session)

            await db.property_parties.update_one(
                {"property_id": PROPERTY_ID},
                {
                    "$set": {
                        "property_id": PROPERTY_ID,
                        "party_id": party["id"],
                        "relationship_type": "OWNER",
                        "authority_status": "VERIFIED",
                        "updated_at": timestamp,
                    },
                    "$setOnInsert": {"id": new_id(), "created_at": timestamp},
                },
                upsert=True,
                session=session,
            )

            await db.advertiser_authorities.update_one(
                {"property_id": PROPERTY_ID},
                {
                    "$set": {
                        "property_id": PROPERTY_ID,
                        "owner_party_id": party["id"],
                        "submitted_by_user_id": advertiser["id"],
                        "authority_basis": "OWNER",
                        "status": "VERIFIED",
                        "updated_at": timestamp,
                    },
                    "$setOnInsert": {"id": new_id(), "created_at": timestamp},
                },
                upsert=True,
                session=session,
            )

            await db.property_parcels.update_one(
                {"property_id": PROPERTY_ID},
                {
                    "$set": {
                        "identifier_scheme": "URBAN_LOT_SECTION",
                        "lot": "2145",
                        "lot_norm": "2145",
                        "section": "1",
                        "section_norm": "1",
                        "portion": None,
                        "portion_norm": None,
                        "location_norm": "LAE",
                    }
                },
                session=session,
            )

            await db.master_properties.update_one(
                {"id": PROPERTY_ID},
                {
                    "$set": {
                        "created_by": advertiser["id"],
                        "lifecycle_status": "active",
                        "verification_status": "VERIFIED",
                        "updated_at": timestamp,
                    }
                },
                session=session,
            )

            await db.listings.update_one(
                {"id": listing["id"]},
                {
                    "$set": {
                        "publication_status": "active",
                        "responsible_channel_active": True,
                        "service": SERVICE,
                        "images": [IMAGE_URL],
                        "updated_at": timestamp,
                    }
                },
                session=session,
            )

            media = await db.listing_media.find_one(
                {"listing_id": listing["id"], "is_cover": True},
                {"_id": 0, "id": 1},
                session=session,
            )
            if not media:
                await db.listing_media.insert_one(
                    {
                        "id": new_id(),
                        "listing_id": listing["id"],
                        "url": IMAGE_URL,
                        "sort_order": 0,
                        "is_cover": True,
                        "created_at": timestamp,
                    },
                    session=session,
                )

            stored = await db.listings.find_one(
                {"id": listing["id"]},
                {"_id": 0, "property_reference": 1},
                session=session,
            )
            property_reference = (stored or {}).get("property_reference")
            if not property_reference:
                year = datetime.fromisoformat(
                    str(listing.get("created_at") or timestamp).replace("Z", "+00:00")
                ).strftime("%y")
                counter_key = f"A{year}"
                counter = await db.property_reference_counters.find_one_and_update(
                    {"id": counter_key},
                    {
                        "$inc": {"sequence": 1},
                        "$setOnInsert": {"id": counter_key, "created_at": timestamp},
                    },
                    upsert=True,
                    return_document=ReturnDocument.AFTER,
                    session=session,
                )
                sequence = int(counter["sequence"])
                if sequence > 9999:
                    raise RuntimeError("Property reference capacity reached")
                property_reference = f"{counter_key}{sequence:04d}"
                await db.listings.update_one(
                    {"id": listing["id"], "property_reference": {"$exists": False}},
                    {"$set": {"property_reference": property_reference}},
                    session=session,
                )

            await db.listing_status_history.insert_one(
                {
                    "id": new_id(),
                    "listing_id": listing["id"],
                    "status": "active",
                    "changed_at": timestamp,
                    "changed_by": advertiser["id"],
                    "reason": "Scoped TEST_IT24 legacy record repair",
                },
                session=session,
            )
            await db.audit_events.insert_one(
                {
                    "id": new_id(),
                    "action": "TEST_RECORD_REPAIRED",
                    "subject_type": "master_property",
                    "subject_id": PROPERTY_ID,
                    "actor_id": advertiser["id"],
                    "created_at": timestamp,
                    "details": {
                        "title": EXPECTED_TITLE,
                        "lot": "2145",
                        "section": "1",
                        "image_added": True,
                        "property_reference": property_reference,
                    },
                },
                session=session,
            )

    repaired = {
        "property_id": PROPERTY_ID,
        "title": EXPECTED_TITLE,
        "lot": "2145",
        "section": "1",
        "advertiser_id": advertiser["id"],
        "call_number": owner_phone,
        "image": IMAGE_URL,
        "property_reference": property_reference,
        "publication_status": "active",
        "verification_status": "VERIFIED",
        "database": DB_NAME,
    }
    print("IT24_REPAIR_COMPLETE=" + str(repaired))
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
