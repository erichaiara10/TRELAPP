"""P3 Legacy Property Backfill v2 — schema-strict version.

Maps every legacy `properties` doc into the P3 integrated graph WITHOUT
relaxing the `master_properties` JSON schema. Requires:
  * a resolvable `property_type_id` via `property_types.name` (case-insensitive)
  * a valid `created_by` — passed in from the caller (typically admin user id)

Idempotent: run key is `legacy_property_id` on master_properties + listings.
Reruns match on that key and update in place; they never create duplicates.

Categories reported per record:
  MIGRATED    — freshly upserted this run (either new or updated)
  MATCHED     — already exists with identical content, no write required
  INCOMPLETE  — required source field missing (title/listing_type/price/property_type)
  FAILED      — schema validator rejected the write

Usage:
    python -m migrations.legacy_backfill_v2 --mode dry-run
    python -m migrations.legacy_backfill_v2 --mode apply --confirmation BACKFILL_P3_V2

For programmatic use call `plan(db, admin_user_id)` for dry-run and
`apply(db, admin_user_id)` for the write path.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

MIGRATION_VERSION = "2026.08.20.p3_legacy_backfill_v2"
CONFIRMATION = "BACKFILL_P3_V2"
NAMESPACE = uuid.UUID("9d6d1ac8-e05d-4a1b-ba8a-9c37ee29f5fa")


def stable_id(kind: str, source_id: str) -> str:
    return str(uuid.uuid5(NAMESPACE, f"legacy:{source_id}:{kind}"))


def clean(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def norm(value: Any) -> Optional[str]:
    cleaned = clean(value)
    return cleaned.upper() if cleaned else None


def positive_number(value: Any) -> Optional[float]:
    try:
        n = float(value)
        return n if n > 0 else None
    except (TypeError, ValueError):
        return None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _load_property_type_index(db) -> Dict[str, Dict[str, Any]]:
    """Return {lower_name: property_type_doc}."""
    index: Dict[str, Dict[str, Any]] = {}
    async for pt in db.property_types.find({}, {"_id": 0}):
        name = clean(pt.get("name"))
        if name:
            index[name.lower()] = pt
    return index


async def _load_location_indexes(db) -> Dict[str, Dict[str, Dict[str, Any]]]:
    provinces = {clean(p.get("name")).lower(): p async for p in db.provinces.find({}, {"_id": 0}) if clean(p.get("name"))}
    cities = {clean(c.get("name")).lower(): c async for c in db.cities.find({}, {"_id": 0}) if clean(c.get("name"))}
    suburbs = {clean(s.get("name")).lower(): s async for s in db.suburbs.find({}, {"_id": 0}) if clean(s.get("name"))}
    return {"provinces": provinces, "cities": cities, "suburbs": suburbs}


def _classify(doc: Dict[str, Any]) -> str:
    if clean(doc.get("full_portion_number")):
        return "PORTION"
    if clean(doc.get("allotment_number")) or clean(doc.get("section_number")):
        return "URBAN_LOT_SECTION"
    return "UNKNOWN"


def _validate(doc: Dict[str, Any], types_by_name: Dict[str, Any]) -> Optional[str]:
    for field in ("title", "listing_type", "property_type"):
        if not clean(doc.get(field)):
            return f"REQUIRED_FIELD_MISSING:{field}"
    if doc.get("listing_type") not in ("sale", "rent"):
        return "LISTING_TYPE_INVALID"
    if positive_number(doc.get("price")) is None:
        return "PRICE_INVALID"
    if clean(doc.get("property_type")).lower() not in types_by_name:
        return f"PROPERTY_TYPE_UNKNOWN:{clean(doc.get('property_type'))}"
    return None


def _plan_records(
    doc: Dict[str, Any],
    types_by_name: Dict[str, Any],
    locations: Dict[str, Any],
    admin_user_id: str,
) -> Dict[str, Dict[str, Any]]:
    """Build every target record for a single legacy doc (P3-schema compliant)."""
    sid = doc["id"]
    property_type = types_by_name[clean(doc.get("property_type")).lower()]
    province = locations["provinces"].get((clean(doc.get("province")) or "").lower())
    city = locations["cities"].get((clean(doc.get("location")) or "").lower())
    suburb = locations["suburbs"].get((clean(doc.get("suburb")) or "").lower())

    property_id = stable_id("master", sid)
    listing_id = stable_id("listing", sid)
    address_id = stable_id("address", sid)
    parcel_id = stable_id("parcel", sid)
    attributes_id = stable_id("attributes", sid)
    price_id = stable_id("price", sid)

    created_at = doc.get("created_at") or now_iso()
    updated_at = now_iso()

    master = {
        "id": property_id,
        "legacy_property_id": sid,
        "property_type_id": property_type["id"],
        "property_type_name": property_type["name"],
        "title": clean(doc.get("title")),
        "lifecycle_status": clean(doc.get("status")) or "active",
        "verification_status": "VERIFIED" if doc.get("verified") else "UNVERIFIED",
        "source_system": "TREL_LEGACY",
        "created_by": admin_user_id,
        "created_at": created_at,
        "updated_at": updated_at,
    }
    address = {
        "id": address_id,
        "property_id": property_id,
        "is_canonical": True,
        "valid_to": None,
        "province_id": (province or {}).get("id"),
        "province_name": clean(doc.get("province")),
        "city_id": (city or {}).get("id"),
        "city_name": clean(doc.get("location")),
        "suburb_id": (suburb or {}).get("id"),
        "suburb_name": clean(doc.get("suburb")),
        "street_name": clean(doc.get("street_name")),
        "street_address": clean(doc.get("address")),
        "nearby_landmark": clean(doc.get("nearby_landmark")),
        "map_coords": clean(doc.get("map_coords")),
        "created_at": updated_at,
    }
    scheme = _classify(doc)
    parcel = {
        "id": parcel_id,
        "property_id": property_id,
        "identifier_scheme": scheme,
        "province_name": clean(doc.get("province")),
        "district_name": clean(doc.get("district")),
        "location_name": clean(doc.get("location")),
        "location_norm": norm(doc.get("location")),
        "suburb_name": clean(doc.get("suburb")),
        "suburb_norm": norm(doc.get("suburb")),
        "street_name": clean(doc.get("street_name")),
        "street_norm": norm(doc.get("street_name")),
        "section": clean(doc.get("section_number")),
        "section_norm": norm(doc.get("section_number")),
        "lot": clean(doc.get("allotment_number")),
        "lot_norm": norm(doc.get("allotment_number")),
        "portion": clean(doc.get("full_portion_number")),
        "portion_norm": norm(doc.get("full_portion_number")),
        "title_reference": clean(doc.get("title_reference")),
        "tenure_type": clean(doc.get("tenure_type")) or None,
        "area_hectares": positive_number(doc.get("total_area_ha")),
        "created_at": updated_at,
    }
    attributes = {
        "id": attributes_id,
        "property_id": property_id,
        "bedrooms": int(doc.get("bedrooms") or 0),
        "bathrooms": int(doc.get("bathrooms") or 0),
        "parking": int(doc.get("parking") or 0),
        "area_sqm": positive_number(doc.get("area_sqm")),
        "features": list(doc.get("features") or []),
        "created_at": updated_at,
        "updated_at": updated_at,
    }
    status = clean(doc.get("status")) or "active"
    listing = {
        "id": listing_id,
        "legacy_property_id": sid,
        "property_id": property_id,
        "title": clean(doc.get("title")),
        "description": clean(doc.get("description")) or "",
        "transaction_type": str(doc.get("listing_type")).upper(),
        "publication_status": status,
        "responsible_channel_active": status in ("active", "under_offer"),
        "price_current": positive_number(doc.get("price")),
        "currency": clean(doc.get("currency")) or "PGK",
        "featured": bool(doc.get("featured")),
        "images": list(doc.get("images") or []),
        "created_at": created_at,
        "updated_at": updated_at,
    }
    price = {
        "id": price_id,
        "listing_id": listing_id,
        "amount": positive_number(doc.get("price")),
        "currency": clean(doc.get("currency")) or "PGK",
        "basis": "TOTAL_SALE" if doc.get("listing_type") == "sale" else "MONTHLY_RENT",
        "effective_from": created_at,
        "created_at": updated_at,
    }
    return {
        "master_properties": master,
        "property_addresses": address,
        "property_parcels": parcel,
        "property_attributes": attributes,
        "listings": listing,
        "listing_prices": price,
    }


async def plan(db, admin_user_id: str) -> Dict[str, Any]:
    """Dry-run: report proposed mapping WITHOUT writing anything."""
    types_by_name = await _load_property_type_index(db)
    locations = await _load_location_indexes(db)
    records: List[Dict[str, Any]] = []
    async for doc in db.properties.find({}):
        sid = clean(doc.get("id"))
        entry: Dict[str, Any] = {"legacy_id": sid, "title": clean(doc.get("title"))}
        issue = _validate(doc, types_by_name)
        if issue:
            entry["category"] = "INCOMPLETE"
            entry["reason"] = issue
            records.append(entry)
            continue
        graph = _plan_records(doc, types_by_name, locations, admin_user_id)
        existing = await db.master_properties.find_one(
            {"legacy_property_id": sid}, {"_id": 0}
        )
        entry["category"] = "MATCHED" if existing else "MIGRATED"
        entry["proposed_master_id"] = graph["master_properties"]["id"]
        entry["proposed_listing_id"] = graph["listings"]["id"]
        entry["property_type_id"] = graph["master_properties"]["property_type_id"]
        entry["property_type_name"] = graph["master_properties"]["property_type_name"]
        entry["identifier_scheme"] = graph["property_parcels"]["identifier_scheme"]
        entry["province"] = graph["property_addresses"]["province_name"]
        entry["province_id_resolved"] = graph["property_addresses"]["province_id"]
        entry["city"] = graph["property_addresses"]["city_name"]
        entry["city_id_resolved"] = graph["property_addresses"]["city_id"]
        entry["suburb"] = graph["property_addresses"]["suburb_name"]
        entry["suburb_id_resolved"] = graph["property_addresses"]["suburb_id"]
        entry["status"] = graph["listings"]["publication_status"]
        entry["price_current"] = graph["listings"]["price_current"]
        records.append(entry)
    summary: Dict[str, Any] = {
        "migration_version": MIGRATION_VERSION,
        "mode": "dry-run",
        "admin_user_id": admin_user_id,
        "source_documents": len(records),
        "by_category": {},
        "records": records,
    }
    for r in records:
        summary["by_category"][r["category"]] = summary["by_category"].get(r["category"], 0) + 1
    return summary


async def apply(db, admin_user_id: str) -> Dict[str, Any]:
    types_by_name = await _load_property_type_index(db)
    locations = await _load_location_indexes(db)
    outcomes: List[Dict[str, Any]] = []
    async for doc in db.properties.find({}):
        sid = clean(doc.get("id"))
        entry: Dict[str, Any] = {"legacy_id": sid, "title": clean(doc.get("title"))}
        issue = _validate(doc, types_by_name)
        if issue:
            entry["category"] = "INCOMPLETE"
            entry["reason"] = issue
            outcomes.append(entry)
            continue
        graph = _plan_records(doc, types_by_name, locations, admin_user_id)
        try:
            for collection, document in graph.items():
                key = (
                    {"legacy_property_id": sid}
                    if collection in {"master_properties", "listings"}
                    else {"property_id": graph["master_properties"]["id"]}
                    if collection in {"property_addresses", "property_parcels", "property_attributes"}
                    else {"listing_id": graph["listings"]["id"]}
                )
                await db[collection].update_one(key, {"$set": document}, upsert=True)
            entry["category"] = "MIGRATED"
            entry["master_id"] = graph["master_properties"]["id"]
            entry["listing_id"] = graph["listings"]["id"]
        except Exception as exc:
            entry["category"] = "FAILED"
            entry["reason"] = f"{type(exc).__name__}: {exc}"[:400]
        outcomes.append(entry)
    summary: Dict[str, Any] = {
        "migration_version": MIGRATION_VERSION,
        "mode": "apply",
        "admin_user_id": admin_user_id,
        "source_documents": len(outcomes),
        "by_category": {},
        "records": outcomes,
    }
    for r in outcomes:
        summary["by_category"][r["category"]] = summary["by_category"].get(r["category"], 0) + 1
    await db.schema_migrations.update_one(
        {"version": MIGRATION_VERSION},
        {"$set": {
            "checksum": "p3-legacy-v2",
            "status": "APPLIED",
            "applied_at": now_iso(),
            "summary": summary["by_category"],
        }},
        upsert=True,
    )
    return summary


async def _resolve_admin_id(db, admin_email: str) -> str:
    admin = await db.users.find_one({"email": admin_email.lower().strip()}, {"_id": 0, "id": 1})
    if not admin:
        raise RuntimeError(f"Admin user {admin_email} not found — cannot backfill without a valid created_by")
    return admin["id"]


async def main_async(args) -> Dict[str, Any]:
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(args.uri)
    try:
        db = client[args.database]
        admin_id = await _resolve_admin_id(db, args.admin_email)
        if args.mode == "dry-run":
            return await plan(db, admin_id)
        return await apply(db, admin_id)
    finally:
        client.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("dry-run", "apply"), default="dry-run")
    parser.add_argument("--confirmation", default="")
    parser.add_argument("--uri", default=os.environ.get("MONGO_URL"))
    parser.add_argument("--database", default=os.environ.get("DB_NAME", "trel_db"))
    parser.add_argument("--admin-email", default=os.environ.get("ADMIN_EMAIL", "admin@trel.com.pg"))
    args = parser.parse_args()
    if args.mode == "apply" and args.confirmation != CONFIRMATION:
        print(f"Apply requires --confirmation {CONFIRMATION}", file=sys.stderr)
        return 2
    if not args.uri:
        print("MONGO_URL or --uri is required", file=sys.stderr)
        return 2
    result = asyncio.run(main_async(args))
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
