import asyncio

from core.db import DB_NAME, client, db, new_id, now_iso

PROPERTY_ID = "a4de4cc0-5f50-50c8-9f4b-ff75aadb5ec5"
EXPECTED_REFERENCE = "A260001"
EXPECTED_TITLE = "TEST_IT24_legal_lp"


async def main():
    if DB_NAME != "trel_test":
        raise RuntimeError(f"Refusing to modify non-test database: {DB_NAME}")

    listing = await db.listings.find_one(
        {"property_id": PROPERTY_ID, "property_reference": EXPECTED_REFERENCE},
        {"_id": 0},
    )
    master = await db.master_properties.find_one({"id": PROPERTY_ID}, {"_id": 0})
    authority = await db.advertiser_authorities.find_one(
        {"property_id": PROPERTY_ID, "status": "VERIFIED"}, {"_id": 0}
    )

    if not listing or listing.get("title") != EXPECTED_TITLE:
        raise RuntimeError("Exact A260001 listing guard failed")
    if not master or master.get("title") != EXPECTED_TITLE:
        raise RuntimeError("Exact A260001 property guard failed")
    if not authority or not authority.get("submitted_by_user_id"):
        raise RuntimeError("Verified advertiser authority is required")
    if listing.get("publication_status") not in {"active", "under_offer"}:
        raise RuntimeError(
            f"A260001 is not available for sale: {listing.get('publication_status')}"
        )
    if master.get("lifecycle_status") != "active":
        raise RuntimeError(
            f"A260001 master property is not active: {master.get('lifecycle_status')}"
        )

    advertiser_id = authority["submitted_by_user_id"]
    timestamp = now_iso()

    async with await client.start_session() as session:
        async with session.start_transaction():
            lifecycle = await db.advertiser_listing_lifecycle.find_one(
                {"user_id": advertiser_id, "listing_id": listing["id"]},
                {"_id": 0},
                session=session,
            ) or {}
            current_status = lifecycle.get("status") or "AVAILABLE"
            current_workflow = lifecycle.get("workflow_status") or "CURRENT"
            if current_status not in {"AVAILABLE", "LIVE"}:
                raise RuntimeError(
                    f"Lifecycle cannot move from {current_status} to SOLD"
                )
            if current_workflow == "ARCHIVED":
                raise RuntimeError("Listing is already archived")

            await db.advertiser_listing_lifecycle.update_one(
                {"user_id": advertiser_id, "listing_id": listing["id"]},
                {
                    "$set": {
                        "status": "SOLD",
                        "workflow_status": "ARCHIVED",
                        "archived_at": timestamp,
                        "updated_at": timestamp,
                    },
                    "$unset": {
                        "next_due": "",
                        "unpublish_due": "",
                        "archive_due": "",
                        "next_reminder_due": "",
                        "confirmation_requested_at": "",
                    },
                    "$setOnInsert": {
                        "id": new_id(),
                        "user_id": advertiser_id,
                        "listing_id": listing["id"],
                        "created_at": timestamp,
                    },
                },
                upsert=True,
                session=session,
            )

            await db.listings.update_one(
                {"id": listing["id"]},
                {
                    "$set": {
                        "publication_status": "sold",
                        "responsible_channel_active": False,
                        "updated_at": timestamp,
                    }
                },
                session=session,
            )
            await db.listing_status_history.insert_one(
                {
                    "id": new_id(),
                    "listing_id": listing["id"],
                    "status": "sold",
                    "changed_at": timestamp,
                    "changed_by": advertiser_id,
                },
                session=session,
            )
            await db.master_properties.update_one(
                {"id": PROPERTY_ID},
                {
                    "$set": {
                        "lifecycle_status": "archived",
                        "archived_at": timestamp,
                        "updated_at": timestamp,
                    }
                },
                session=session,
            )
            await db.audit_events.insert_many(
                [
                    {
                        "id": new_id(),
                        "action": "ADVERTISER_LISTING_LIFECYCLE_CHANGED",
                        "subject_type": "advertiser_listing",
                        "subject_id": listing["id"],
                        "actor_id": advertiser_id,
                        "previous_status": current_status,
                        "new_status": "SOLD",
                        "status": "SOLD",
                        "created_at": timestamp,
                    },
                    {
                        "id": new_id(),
                        "action": "ADVERTISER_LISTING_ARCHIVED",
                        "subject_type": "property_listing",
                        "subject_id": listing["id"],
                        "actor_id": advertiser_id,
                        "previous_status": current_workflow,
                        "new_status": "ARCHIVED",
                        "status": "ARCHIVED",
                        "reason": "Listing closed as SOLD",
                        "created_at": timestamp,
                    },
                ],
                session=session,
            )

    final_listing = await db.listings.find_one(
        {"id": listing["id"]},
        {"_id": 0, "publication_status": 1, "responsible_channel_active": 1},
    )
    final_master = await db.master_properties.find_one(
        {"id": PROPERTY_ID},
        {"_id": 0, "lifecycle_status": 1, "archived_at": 1},
    )
    final_lifecycle = await db.advertiser_listing_lifecycle.find_one(
        {"user_id": advertiser_id, "listing_id": listing["id"]},
        {"_id": 0, "status": 1, "workflow_status": 1},
    )
    if final_listing != {
        "publication_status": "sold",
        "responsible_channel_active": False,
    }:
        raise RuntimeError(f"Listing verification failed: {final_listing}")
    if (final_master or {}).get("lifecycle_status") != "archived":
        raise RuntimeError(f"Master archive verification failed: {final_master}")
    if final_lifecycle != {"status": "SOLD", "workflow_status": "ARCHIVED"}:
        raise RuntimeError(f"Lifecycle verification failed: {final_lifecycle}")

    print(
        "A260001_SOLD_ARCHIVED="
        + str(
            {
                "property_reference": EXPECTED_REFERENCE,
                "listing_status": "sold",
                "workflow_status": "ARCHIVED",
                "master_status": "archived",
                "database": DB_NAME,
            }
        )
    )
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
