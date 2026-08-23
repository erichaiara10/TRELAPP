"""One-off cleanup of TEST_ITER28/TEST_ITER29 property artefacts from the integrated graph."""
import asyncio
import os

from dotenv import dotenv_values
from motor.motor_asyncio import AsyncIOMotorClient

env = dotenv_values("/app/backend/.env")
MONGO_URL = os.environ.get("MONGO_URL") or env.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME") or env.get("DB_NAME")


async def main():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    rx = {"$regex": "TEST_ITER2[89]"}
    listings = await db.listings.find({"title": rx}, {"id": 1, "property_id": 1, "_id": 0}).to_list(500)
    prop_ids = [row.get("property_id") for row in listings if row.get("property_id")]
    listing_ids = [row["id"] for row in listings]
    print("listings", len(listing_ids), "props", len(prop_ids))
    if listing_ids:
        print("listings del", (await db.listings.delete_many({"id": {"$in": listing_ids}})).deleted_count)
    if prop_ids:
        for coll in ("master_properties", "property_parcels", "property_addresses",
                     "property_party_roles", "property_features", "property_media",
                     "property_authorities", "listing_price_history"):
            if coll in await db.list_collection_names():
                res = await db[coll].delete_many({"property_id": {"$in": prop_ids}})
                print(coll, res.deleted_count)
        print("master by id", (await db.master_properties.delete_many({"id": {"$in": prop_ids}})).deleted_count)
    print("parties", (await db.parties.delete_many({"full_name": rx})).deleted_count)
    print("legacy properties", (await db.properties.delete_many({"title": rx})).deleted_count)
    client.close()


asyncio.run(main())
