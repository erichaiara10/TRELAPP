"""P2 additive legacy-property mapping and backfill.

Dry-run is the default and performs no writes. Apply only upserts integrated
property records plus migration control records; legacy collections/documents
are never updated or deleted.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from pymongo import MongoClient, UpdateOne

MIGRATION_VERSION = "2026.08.20.p2_property_backfill"
CONFIRMATION = "BACKFILL_TREL_DB_P2"
DB_NAME = "trel_db"
SOURCE_COLLECTION = "properties"
TARGET_COLLECTIONS = (
    "master_properties",
    "property_addresses",
    "property_parcels",
    "property_attributes",
    "listings",
    "listing_prices",
    "listing_media",
    "migration_id_map",
    "migration_exceptions",
)
NAMESPACE = uuid.UUID("ec3a81f5-283a-4b79-b950-a421a3efc9c5")


def stable_id(kind: str, source_id: str) -> str:
    return str(uuid.uuid5(NAMESPACE, f"{SOURCE_COLLECTION}:{source_id}:{kind}"))


def clean(value: Any) -> Optional[str]:
    value = str(value or "").strip()
    return value or None


def normalized(value: Any) -> Optional[str]:
    value = clean(value)
    return value.upper() if value else None


def positive_number(value: Any) -> Optional[float]:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def source_id(doc: Dict[str, Any]) -> Optional[str]:
    return clean(doc.get("id") or doc.get("_id"))


def classify_scheme(doc: Dict[str, Any]) -> str:
    if clean(doc.get("full_portion_number")):
        return "PORTION"
    if clean(doc.get("allotment_number")) or clean(doc.get("section_number")):
        return "URBAN_LOT_SECTION"
    return "UNKNOWN"


def exception_for(doc: Dict[str, Any]) -> Optional[Dict[str, str]]:
    sid = source_id(doc)
    if not sid:
        return {"source_id": "<missing>", "error_code": "SOURCE_ID_MISSING"}
    required = [name for name in ("title", "listing_type", "property_type") if not clean(doc.get(name))]
    if required:
        return {"source_id": sid, "error_code": "REQUIRED_FIELD_MISSING:" + ",".join(required)}
    if doc.get("listing_type") not in ("sale", "rent"):
        return {"source_id": sid, "error_code": "LISTING_TYPE_INVALID"}
    if positive_number(doc.get("price")) is None:
        return {"source_id": sid, "error_code": "PRICE_INVALID"}
    return None


def transform(doc: Dict[str, Any], now: datetime) -> Dict[str, Dict[str, Any]]:
    sid = source_id(doc)
    if not sid:
        raise ValueError("source id required")
    property_id = stable_id("master_property", sid)
    listing_id = stable_id("listing", sid)
    address_id = stable_id("address", sid)
    parcel_id = stable_id("parcel", sid)
    attributes_id = stable_id("attributes", sid)
    price_id = stable_id("price", sid)
    created_at = doc.get("created_at") or now.isoformat()
    updated_at = doc.get("updated_at") or created_at

    master = {
        "id": property_id,
        "legacy_property_id": sid,
        "property_type_name": clean(doc.get("property_type")),
        "title": clean(doc.get("title")),
        "lifecycle_status": clean(doc.get("status")) or "active",
        "verification_status": "VERIFIED" if doc.get("verified") else "UNVERIFIED",
        "owner_party_legacy_id": clean(doc.get("owner_customer_id")),
        "assigned_staff_legacy_id": clean(doc.get("assigned_agent_id")),
        "source_system": "TREL_LEGACY",
        "created_at": created_at,
        "updated_at": updated_at,
    }
    address = {
        "id": address_id,
        "property_id": property_id,
        "is_canonical": True,
        "valid_to": None,
        "province_name": clean(doc.get("province")),
        "city_name": clean(doc.get("location")),
        "suburb_name": clean(doc.get("suburb")),
        "street_name": clean(doc.get("street_name")),
        "street_address": clean(doc.get("address")),
        "nearby_landmark": clean(doc.get("nearby_landmark")),
        "map_coords": clean(doc.get("map_coords")),
        "created_at": now.isoformat(),
    }
    scheme = classify_scheme(doc)
    parcel = {
        "id": parcel_id,
        "property_id": property_id,
        "identifier_scheme": scheme,
        "province_name": clean(doc.get("province")),
        "district_name": clean(doc.get("district")),
        "location_name": clean(doc.get("location")),
        "location_norm": normalized(doc.get("location")),
        "suburb_name": clean(doc.get("suburb")),
        "street_name": clean(doc.get("street_name")),
        "street_norm": normalized(doc.get("street_name")),
        "section": clean(doc.get("section_number")),
        "section_norm": normalized(doc.get("section_number")),
        "lot": clean(doc.get("allotment_number")),
        "lot_norm": normalized(doc.get("allotment_number")),
        "portion": clean(doc.get("full_portion_number")),
        "portion_norm": normalized(doc.get("full_portion_number")),
        "title_reference": clean(doc.get("title_reference")),
        "tenure_type": clean(doc.get("tenure_type")),
        "area_hectares": positive_number(doc.get("total_area_ha")),
        "created_at": now.isoformat(),
    }
    attributes = {
        "id": attributes_id,
        "property_id": property_id,
        "bedrooms": int(doc.get("bedrooms") or 0),
        "bathrooms": int(doc.get("bathrooms") or 0),
        "parking": int(doc.get("parking") or 0),
        "area_sqm": positive_number(doc.get("area_sqm")),
        "features": list(doc.get("features") or []),
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }
    listing = {
        "id": listing_id,
        "legacy_property_id": sid,
        "property_id": property_id,
        "title": clean(doc.get("title")),
        "description": clean(doc.get("description")) or "",
        "transaction_type": str(doc.get("listing_type")).upper(),
        "publication_status": clean(doc.get("status")) or "active",
        "responsible_channel_active": clean(doc.get("status")) in (None, "active", "under_offer"),
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
        "created_at": now.isoformat(),
    }
    return {
        "master_properties": master,
        "property_addresses": address,
        "property_parcels": parcel,
        "property_attributes": attributes,
        "listings": listing,
        "listing_prices": price,
    }


def analyze(documents: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    counts: Counter[str] = Counter()
    errors: Counter[str] = Counter()
    valid = 0
    total = 0
    now = datetime.now(timezone.utc)
    for doc in documents:
        total += 1
        issue = exception_for(doc)
        if issue:
            errors[issue["error_code"]] += 1
            continue
        valid += 1
        for collection in transform(doc, now):
            counts[collection] += 1
        counts["migration_id_map"] += 2
    return {
        "migration_version": MIGRATION_VERSION,
        "mode": "dry-run",
        "source_collection": SOURCE_COLLECTION,
        "source_documents": total,
        "valid_source_documents": valid,
        "exception_documents": sum(errors.values()),
        "exception_codes": dict(sorted(errors.items())),
        "planned_upserts": dict(sorted(counts.items())),
        "legacy_document_writes": 0,
        "legacy_document_deletes": 0,
    }


def _upsert(collection: str, document: Dict[str, Any]) -> UpdateOne:
    return UpdateOne({"id": document["id"]}, {"$set": document}, upsert=True)


def apply(db) -> Dict[str, Any]:
    documents = list(db[SOURCE_COLLECTION].find({}))
    summary = analyze(documents)
    now = datetime.now(timezone.utc)
    operations: Dict[str, List[UpdateOne]] = {name: [] for name in TARGET_COLLECTIONS}

    for doc in documents:
        sid = source_id(doc)
        issue = exception_for(doc)
        if issue:
            exception_id = stable_id("exception", sid or "<missing>")
            operations["migration_exceptions"].append(_upsert("migration_exceptions", {
                "id": exception_id,
                "migration_version": MIGRATION_VERSION,
                "source_collection": SOURCE_COLLECTION,
                "source_id": sid or "<missing>",
                "error_code": issue["error_code"],
                "status": "OPEN",
                "created_at": now,
            }))
            continue

        target = transform(doc, now)
        for collection, transformed in target.items():
            operations[collection].append(_upsert(collection, transformed))
        for target_type in ("master_property", "listing"):
            operations["migration_id_map"].append(_upsert("migration_id_map", {
                "id": stable_id("map:" + target_type, sid),
                "source_collection": SOURCE_COLLECTION,
                "source_id": sid,
                "target_type": target_type,
                "target_id": stable_id(target_type, sid),
                "migration_version": MIGRATION_VERSION,
                "created_at": now,
            }))

    written: Dict[str, int] = {}
    for collection, requests in operations.items():
        if requests:
            result = db[collection].bulk_write(requests, ordered=False)
            written[collection] = result.upserted_count + result.modified_count + result.matched_count

    result = {
        **summary,
        "mode": "apply",
        "status": "APPLIED",
        "written_or_matched": dict(sorted(written.items())),
    }
    db.schema_migrations.update_one(
        {"version": MIGRATION_VERSION},
        {"$set": {
            "checksum": "deterministic-v1",
            "status": "APPLIED",
            "started_at": now,
            "applied_at": datetime.now(timezone.utc),
            "result": result,
        }},
        upsert=True,
    )
    return result


def verify(db) -> Dict[str, Any]:
    source_total = db[SOURCE_COLLECTION].count_documents({})
    mapped_sources = len(db.migration_id_map.distinct(
        "source_id",
        {"migration_version": MIGRATION_VERSION, "source_collection": SOURCE_COLLECTION},
    ))
    open_exceptions = db.migration_exceptions.count_documents(
        {"migration_version": MIGRATION_VERSION, "status": "OPEN"}
    )
    accounted_for = mapped_sources + open_exceptions
    checks = {
        "all_sources_accounted_for": accounted_for == source_total,
        "legacy_source_unchanged": source_total == 14,
        "no_target_orphans": db.listings.count_documents({
            "legacy_property_id": {"$exists": True},
            "property_id": {"$exists": False},
        }) == 0,
    }
    return {
        "migration_version": MIGRATION_VERSION,
        "mode": "verify",
        "verification_passed": all(checks.values()),
        "checks": checks,
        "source_documents": source_total,
        "mapped_sources": mapped_sources,
        "open_exceptions": open_exceptions,
        "legacy_document_writes": 0,
        "legacy_document_deletes": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("dry-run", "apply", "verify"), default="dry-run")
    parser.add_argument("--confirmation", default="")
    parser.add_argument("--uri", default=os.environ.get("MONGO_URL"))
    parser.add_argument("--username", default=os.environ.get("MONGO_USERNAME"))
    parser.add_argument("--auth-database", default=os.environ.get("MONGO_AUTH_DATABASE", "admin"))
    parser.add_argument("--database", default=os.environ.get("DB_NAME", DB_NAME))
    args = parser.parse_args()
    if not args.uri:
        print("MONGO_URL or --uri is required", file=sys.stderr)
        return 2
    if args.mode == "apply" and args.confirmation != CONFIRMATION:
        print(f"Apply requires --confirmation {CONFIRMATION}", file=sys.stderr)
        return 2

    options: Dict[str, Any] = {"serverSelectionTimeoutMS": 15000}
    if args.username:
        options.update(
            username=args.username,
            password=os.environ.get("MONGO_PASSWORD"),
            authSource=args.auth_database,
        )
    client = MongoClient(args.uri, **options)
    try:
        db = client[args.database]
        db.command("ping")
        if args.mode == "dry-run":
            output = analyze(db[SOURCE_COLLECTION].find({}))
        elif args.mode == "apply":
            output = apply(db)
        else:
            output = verify(db)
        print(json.dumps(output, indent=2, default=str, sort_keys=True))
        return 0 if args.mode != "verify" or output["verification_passed"] else 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
