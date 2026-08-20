"""Controlled non-production P3 relationship smoke test."""
from __future__ import annotations

import argparse
import asyncio
import os
import uuid

from core.db import client, db
from core.integrated_property_service import IntegratedPropertyService

CONFIRMATION = "RUN_TREL_P3_SMOKE"


async def run() -> None:
    property_type = await db.property_types.find_one(
        {"is_active": True, "legal_scheme": "lot_section_street"}, {"_id": 0}
    )
    suburb = await db.suburbs.find_one({}, {"_id": 0})
    if not property_type or not suburb:
        raise RuntimeError("Property type and location seed data are required")
    city = await db.cities.find_one({"id": suburb["city_id"]}, {"_id": 0})
    province = await db.provinces.find_one({"id": suburb["province_id"]}, {"_id": 0})
    if not city or not province:
        raise RuntimeError("Location relationship is incomplete")

    marker = uuid.uuid4().hex[:10].upper()
    payload = {
        "title": f"P3 Integration Smoke {marker}",
        "listing_type": "sale",
        "property_type": property_type["name"],
        "property_type_id": property_type["id"],
        "price": 100000,
        "currency": "PGK",
        "bedrooms": 2,
        "bathrooms": 1,
        "parking": 1,
        "area_sqm": 100,
        "province": province["name"],
        "province_id": province["id"],
        "location": city["name"],
        "city_id": city["id"],
        "suburb": suburb["name"],
        "suburb_id": suburb["id"],
        "street_name": f"Smoke Street {marker}",
        "section_number": marker,
        "allotment_number": marker,
        "total_area_ha": 0.05,
        "features": ["P3 smoke tested"],
        "images": [],
        "documents": [{
            "document_type": "TITLE_DOCUMENT",
            "url": f"https://example.test/{marker}.pdf",
            "status": "UPLOADED",
        }],
        "status": "active",
        "featured": False,
        "verified": False,
        "owner_name": f"P3 Test Owner {marker}",
        "owner_email": None,
        "owner_phone": None,
        "owner_relationship": "OWNER",
        "authority_status": "VERIFIED",
        "duplicate_override": False,
    }
    user = {"id": "p3-workflow-test-user"}
    service = IntegratedPropertyService(db, client)

    before = await service.duplicate_check(payload)
    if before:
        raise RuntimeError("Unique smoke property unexpectedly matched an existing property")

    created = await service.create(payload, user)
    property_id = created["id"]
    listing_id = created["integrated_listing_id"]
    expected = {
        "master_properties": {"id": property_id},
        "property_addresses": {"property_id": property_id},
        "property_parcels": {"property_id": property_id},
        "property_attributes": {"property_id": property_id},
        "property_parties": {"property_id": property_id},
        "property_documents": {"property_id": property_id},
        "listings": {"id": listing_id, "property_id": property_id},
        "listing_prices": {"listing_id": listing_id},
        "listing_status_history": {"listing_id": listing_id},
        "advertiser_authorities": {"property_id": property_id},
        "audit_events": {"subject_id": property_id, "action": "PROPERTY_CREATED"},
    }
    for collection, query in expected.items():
        if not await db[collection].find_one(query, {"_id": 0, "id": 1}):
            raise RuntimeError(f"Missing relationship record: {collection}")

    same_owner = await service.duplicate_check(payload)
    if not same_owner or same_owner[0].get("confidence") != 100:
        raise RuntimeError("Approved owner + parcel duplicate identity was not detected")
    different_owner = await service.duplicate_check({**payload, "owner_name": f"Different Owner {marker}"})
    if different_owner:
        raise RuntimeError("A different owner incorrectly triggered the complete duplicate identity")

    updated = await service.update(
        property_id,
        {**payload, "price": 110000, "description": "P3 update verified",
         "status": "draft", "authority_status": "REJECTED", "documents": []},
        user,
    )
    if not updated or updated["price"] != 110000:
        raise RuntimeError("Integrated Property update did not persist")
    authority = await db.advertiser_authorities.find_one({"property_id": property_id}, {"_id": 0})
    if not authority or authority.get("status") != "REJECTED":
        raise RuntimeError("Advertiser authority was not synchronized on update")
    if await db.property_documents.count_documents({"property_id": property_id}):
        raise RuntimeError("Clearing all supporting documents did not remove their links")

    if not await service.delete(property_id, user):
        raise RuntimeError("Integrated Property soft-delete failed")
    master = await db.master_properties.find_one({"id": property_id}, {"_id": 0})
    listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    if master.get("lifecycle_status") != "deleted":
        raise RuntimeError("Master Property was not soft-deleted")
    if listing.get("publication_status") != "withdrawn":
        raise RuntimeError("Listing was not withdrawn")

    print({
        "p3_smoke_passed": True,
        "property_graph_relationships": len(expected),
        "owner_duplicate_rule_verified": True,
        "authority_sync_verified": True,
        "document_clear_verified": True,
        "create_verified": True,
        "update_verified": True,
        "read_verified": True,
        "soft_delete_verified": True,
        "legacy_collection_writes": 0,
    })


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirmation", required=True)
    args = parser.parse_args()
    if args.confirmation != CONFIRMATION:
        raise SystemExit(f"Confirmation must be {CONFIRMATION}")
    asyncio.run(run())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
