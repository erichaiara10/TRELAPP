import asyncio
import json

from core.db import DB_NAME, client, db

PROPERTY_ID = "a4de4cc0-5f50-50c8-9f4b-ff75aadb5ec5"
ADVERTISER_EMAIL = "pai.erebo@unitygroup.com.pg"


def clean(document):
    if not document:
        return None
    return {key: value for key, value in document.items() if key != "_id"}


async def main():
    if DB_NAME != "trel_test":
        raise RuntimeError(f"Refusing to inspect non-test database: {DB_NAME}")

    master = await db.master_properties.find_one({"id": PROPERTY_ID}, {"_id": 0})
    listing = await db.listings.find_one(
        {"property_id": PROPERTY_ID},
        {"_id": 0},
        sort=[("responsible_channel_active", -1), ("updated_at", -1)],
    )
    listing_id = (listing or {}).get("id")
    advertiser = await db.users.find_one(
        {"email": {"$regex": f"^{ADVERTISER_EMAIL}$", "$options": "i"}},
        {"_id": 0, "id": 1, "name": 1, "email": 1, "phone": 1,
         "account_category": 1, "status": 1},
    )
    advertiser_id = (advertiser or {}).get("id")
    profile = await db.advertiser_profiles.find_one(
        {"user_id": advertiser_id},
        {"_id": 0, "user_id": 1, "status": 1, "whatsapp": 1,
         "advertiser_relationship_type": 1},
    ) if advertiser else None

    result = {
        "database": DB_NAME,
        "master": clean(master),
        "property_type": clean(await db.property_types.find_one(
            {"id": (master or {}).get("property_type_id")}, {"_id": 0}
        )),
        "listing": clean(listing),
        "address": clean(await db.property_addresses.find_one(
            {"property_id": PROPERTY_ID}, {"_id": 0}
        )),
        "parcel": clean(await db.property_parcels.find_one(
            {"property_id": PROPERTY_ID}, {"_id": 0}
        )),
        "attributes": clean(await db.property_attributes.find_one(
            {"property_id": PROPERTY_ID}, {"_id": 0}
        )),
        "authority": clean(await db.advertiser_authorities.find_one(
            {"property_id": PROPERTY_ID}, {"_id": 0}
        )),
        "party_link": clean(await db.property_parties.find_one(
            {"property_id": PROPERTY_ID}, {"_id": 0}
        )),
        "media": [
            clean(row) for row in await db.listing_media.find(
                {"listing_id": listing_id}, {"_id": 0}
            ).sort("sort_order", 1).to_list(20)
        ] if listing_id else [],
        "advertiser_candidate": clean(advertiser),
        "advertiser_profile": clean(profile),
        "advertiser_identity_documents": [
            clean(row) for row in await db.identity_documents.find(
                {"user_id": advertiser_id}, {"_id": 0, "id": 1, "document_type": 1, "status": 1}
            ).to_list(20)
        ] if advertiser_id else [],
    }
    print("IT24_INSPECTION=" + json.dumps(result, default=str, sort_keys=True))
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
