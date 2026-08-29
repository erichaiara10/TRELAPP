"""P3 integrated Property schema hardening.

Applies full field-level validators and relationship indexes to the integrated
Property graph. It never modifies or deletes business documents.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from pymongo import ASCENDING, DESCENDING, MongoClient

MIGRATION_VERSION = "2026.08.20.p3_integrated_property"
CONFIRMATION = "APPLY_TREL_DB_P3"
DB_NAME = "trel_db"


def _schema(required: Sequence[str], properties: Dict[str, Any]) -> Dict[str, Any]:
    return {"$jsonSchema": {
        "bsonType": "object",
        "required": list(required),
        "properties": properties,
    }}


STRING = {"bsonType": "string", "minLength": 1}
NULLABLE_STRING = {"bsonType": ["string", "null"]}
NUMBER = {"bsonType": ["double", "int", "long", "decimal"]}
NULLABLE_NUMBER = {"bsonType": ["double", "int", "long", "decimal", "null"]}
ISO_DATE = {"bsonType": "string", "minLength": 10}

VALIDATORS: Dict[str, Dict[str, Any]] = {
    "master_properties": _schema(
        ["id", "property_type_id", "property_type_name", "lifecycle_status",
         "verification_status", "created_by", "created_at", "updated_at"],
        {
            "id": STRING,
            "property_type_id": STRING,
            "property_type_name": STRING,
            "title": STRING,
            "lifecycle_status": {"enum": ["draft", "active", "under_offer", "sold", "leased", "withdrawn", "archived", "deleted"]},
            "verification_status": {"enum": ["UNVERIFIED", "PENDING", "VERIFIED", "REJECTED"]},
            "parent_property_id": NULLABLE_STRING,
            "created_by": STRING,
            "created_at": ISO_DATE,
            "updated_at": ISO_DATE,
        },
    ),
    "property_addresses": _schema(
        ["id", "property_id", "province_id", "city_id", "suburb_id",
         "is_canonical", "created_at"],
        {
            "id": STRING, "property_id": STRING, "province_id": STRING,
            "city_id": STRING, "suburb_id": STRING,
            "district_id": NULLABLE_STRING, "local_area_id": NULLABLE_STRING,
            "street_id": NULLABLE_STRING, "street_name": NULLABLE_STRING,
            "street_address": NULLABLE_STRING, "nearby_landmark": NULLABLE_STRING,
            "map_coords": NULLABLE_STRING, "is_canonical": {"bsonType": "bool"},
            "valid_to": {"bsonType": ["string", "date", "null"]},
            "created_at": ISO_DATE,
        },
    ),
    "property_parcels": _schema(
        ["id", "property_id", "identifier_scheme", "province_id", "created_at"],
        {
            "id": STRING, "property_id": STRING,
            "identifier_scheme": {"enum": ["URBAN_LOT_SECTION", "PORTION", "CUSTOMARY"]},
            "province_id": STRING, "district_id": NULLABLE_STRING,
            "city_id": NULLABLE_STRING, "suburb_id": NULLABLE_STRING,
            "street_id": NULLABLE_STRING, "street_norm": NULLABLE_STRING,
            "section": NULLABLE_STRING, "section_norm": NULLABLE_STRING,
            "lot": NULLABLE_STRING, "lot_norm": NULLABLE_STRING,
            "location_norm": NULLABLE_STRING, "portion": NULLABLE_STRING,
            "portion_norm": NULLABLE_STRING, "title_reference": NULLABLE_STRING,
            "tenure_type": {"enum": ["STATE_LEASE", "FREEHOLD", "CUSTOMARY", "OTHER", None]},
            "area_hectares": NULLABLE_NUMBER, "created_at": ISO_DATE,
        },
    ),
    "property_attributes": _schema(
        ["id", "property_id", "created_at", "updated_at"],
        {
            "id": STRING, "property_id": STRING,
            "bedrooms": {"bsonType": ["int", "long"], "minimum": 0},
            "bathrooms": {"bsonType": ["int", "long"], "minimum": 0},
            "parking": {"bsonType": ["int", "long"], "minimum": 0},
            "area_sqm": NULLABLE_NUMBER, "features": {"bsonType": "array"},
            "created_at": ISO_DATE, "updated_at": ISO_DATE,
        },
    ),
    "property_parties": _schema(
        ["id", "property_id", "party_id", "relationship_type",
         "authority_status", "created_at"],
        {
            "id": STRING, "property_id": STRING, "party_id": STRING,
            "relationship_type": {"enum": ["OWNER", "JOINT_OWNER", "AUTHORISED_AGENT", "AUTHORISED_REPRESENTATIVE"]},
            "authority_status": {"enum": ["PENDING", "VERIFIED", "REJECTED", "EXPIRED"]},
            "created_at": ISO_DATE,
        },
    ),
    "property_documents": _schema(
        ["id", "property_id", "document_type", "url", "status", "created_at"],
        {
            "id": STRING, "property_id": STRING, "document_type": STRING,
            "url": STRING, "status": {"enum": ["UPLOADED", "PENDING_REVIEW", "VERIFIED", "REJECTED"]},
            "created_at": ISO_DATE,
        },
    ),
    "listings": _schema(
        ["id", "property_id", "transaction_type", "publication_status",
         "responsible_channel_active", "price_current", "currency",
         "created_at", "updated_at"],
        {
            "id": STRING, "property_id": STRING,
            "transaction_type": {"enum": ["SALE", "RENT"]},
            "publication_status": {"enum": ["draft", "active", "under_offer", "sold", "leased", "withdrawn"]},
            "responsible_channel_active": {"bsonType": "bool"},
            "price_current": NUMBER, "currency": STRING, "title": STRING,
            "description": {"bsonType": "string"}, "featured": {"bsonType": "bool"},
            "created_at": ISO_DATE, "updated_at": ISO_DATE,
        },
    ),
    "listing_prices": _schema(
        ["id", "listing_id", "amount", "currency", "basis",
         "effective_from", "created_at"],
        {
            "id": STRING, "listing_id": STRING, "amount": NUMBER,
            "currency": STRING,
            "basis": {"enum": ["TOTAL_SALE", "MONTHLY_RENT"]},
            "effective_from": ISO_DATE, "created_at": ISO_DATE,
        },
    ),
    "listing_media": _schema(
        ["id", "listing_id", "url", "sort_order", "is_cover", "created_at"],
        {
            "id": STRING, "listing_id": STRING, "url": STRING,
            "sort_order": {"bsonType": ["int", "long"], "minimum": 0},
            "is_cover": {"bsonType": "bool"}, "created_at": ISO_DATE,
        },
    ),
    "listing_features": _schema(
        ["id", "listing_id", "feature_id", "created_at"],
        {"id": STRING, "listing_id": STRING, "feature_id": STRING, "created_at": ISO_DATE},
    ),
    "listing_status_history": _schema(
        ["id", "listing_id", "status", "changed_at", "changed_by"],
        {
            "id": STRING, "listing_id": STRING,
            "status": {"enum": ["draft", "active", "under_offer", "sold", "leased", "withdrawn"]},
            "changed_at": ISO_DATE, "changed_by": STRING,
        },
    ),
}

IndexSpec = Tuple[str, str, Sequence[Tuple[str, int]], Dict[str, Any]]
INDEXES: Sequence[IndexSpec] = (
    ("property_attributes", "ux_property_attributes", (("property_id", ASCENDING),), {"unique": True}),
    ("property_parcels", "ix_duplicate_urban", (
        ("province_id", ASCENDING), ("suburb_id", ASCENDING),
        ("street_norm", ASCENDING), ("section_norm", ASCENDING), ("lot_norm", ASCENDING),
    ), {"partialFilterExpression": {"identifier_scheme": "URBAN_LOT_SECTION"}}),
    ("property_parcels", "ix_duplicate_portion", (
        ("province_id", ASCENDING), ("district_id", ASCENDING),
        ("location_norm", ASCENDING), ("portion_norm", ASCENDING),
    ), {"partialFilterExpression": {"identifier_scheme": {"$in": ["PORTION", "CUSTOMARY"]}}}),
    ("property_parties", "ux_property_party_relationship", (
        ("property_id", ASCENDING), ("party_id", ASCENDING), ("relationship_type", ASCENDING),
    ), {"unique": True}),
    ("listing_features", "ux_listing_feature", (
        ("listing_id", ASCENDING), ("feature_id", ASCENDING),
    ), {"unique": True}),
    ("property_documents", "ix_property_documents", (
        ("property_id", ASCENDING), ("document_type", ASCENDING), ("status", ASCENDING),
    ), {}),
    ("listings", "ix_property_listing_history", (
        ("property_id", ASCENDING), ("created_at", DESCENDING),
    ), {}),
)


def checksum() -> str:
    payload = {
        "version": MIGRATION_VERSION,
        "validators": VALIDATORS,
        "indexes": [[c, n, list(k), o] for c, n, k, o in INDEXES],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _equivalent(existing: Iterable[Dict[str, Any]], keys, options) -> bool:
    for item in existing:
        if list(item.get("key", {}).items()) != list(keys):
            continue
        if bool(item.get("unique")) != bool(options.get("unique")):
            continue
        if item.get("partialFilterExpression") != options.get("partialFilterExpression"):
            continue
        return True
    return False


def plan(db) -> Dict[str, Any]:
    names = set(db.list_collection_names())
    missing = sorted(set(VALIDATORS) - names)
    indexes = []
    for collection, name, keys, options in INDEXES:
        existing = list(db[collection].list_indexes()) if collection in names else []
        if not _equivalent(existing, keys, options):
            indexes.append({"collection": collection, "name": name})
    return {
        "migration_version": MIGRATION_VERSION,
        "checksum": checksum(),
        "mode": "dry-run",
        "validator_updates": sorted(VALIDATORS),
        "missing_collections": missing,
        "index_creates": indexes,
        "business_document_writes": 0,
        "business_document_deletes": 0,
    }


def apply(db) -> Dict[str, Any]:
    result = plan(db)
    if result["missing_collections"]:
        raise RuntimeError("P1 collections missing: " + ", ".join(result["missing_collections"]))
    existing = db.schema_migrations.find_one({"version": MIGRATION_VERSION})
    if existing and existing.get("status") == "APPLIED":
        if existing.get("checksum") != checksum():
            raise RuntimeError("Applied P3 checksum differs from source")
        return {"status": "ALREADY_APPLIED", **result}

    started = datetime.now(timezone.utc)
    db.schema_migrations.update_one(
        {"version": MIGRATION_VERSION},
        {"$set": {"checksum": checksum(), "status": "RUNNING", "last_attempt_at": started},
         "$setOnInsert": {"started_at": started}},
        upsert=True,
    )
    for collection, validator in VALIDATORS.items():
        db.command({
            "collMod": collection,
            "validator": validator,
            "validationLevel": "strict",
            "validationAction": "error",
        })
    created = []
    for collection, name, keys, options in INDEXES:
        if _equivalent(db[collection].list_indexes(), keys, options):
            continue
        db[collection].create_index(list(keys), name=name, **options)
        created.append(f"{collection}.{name}")
    outcome = {
        "status": "APPLIED",
        "migration_version": MIGRATION_VERSION,
        "checksum": checksum(),
        "validators_applied": len(VALIDATORS),
        "indexes_created": created,
        "business_document_writes": 0,
        "business_document_deletes": 0,
    }
    db.schema_migrations.update_one(
        {"version": MIGRATION_VERSION},
        {"$set": {"status": "APPLIED", "applied_at": datetime.now(timezone.utc), "result": outcome}},
    )
    return outcome


def recreate_empty(db) -> Dict[str, Any]:
    """Recreate only empty P1 collections when collMod is unavailable.

    The operation aborts before any drop if a target contains a document. Existing
    non-_id indexes are captured and restored before P3 indexes are added.
    """
    counts = {
        collection: db[collection].count_documents({}, limit=1)
        for collection in VALIDATORS
    }
    non_empty = sorted(name for name, count in counts.items() if count)
    if non_empty:
        raise RuntimeError(
            "Empty-collection fallback refused; data exists in: "
            + ", ".join(non_empty)
        )

    captured: Dict[str, List[Dict[str, Any]]] = {}
    for collection in VALIDATORS:
        captured[collection] = [
            item for item in db[collection].list_indexes()
            if item.get("name") != "_id_"
        ]

    for collection, validator in VALIDATORS.items():
        db.drop_collection(collection)
        db.create_collection(
            collection,
            validator=validator,
            validationLevel="strict",
            validationAction="error",
        )
        for item in captured[collection]:
            options = {
                key: item[key]
                for key in (
                    "name", "unique", "sparse", "expireAfterSeconds",
                    "partialFilterExpression", "collation", "hidden",
                )
                if key in item
            }
            db[collection].create_index(
                list(item["key"].items()),
                **options,
            )

    created = []
    for collection, name, keys, options in INDEXES:
        if _equivalent(db[collection].list_indexes(), keys, options):
            continue
        db[collection].create_index(list(keys), name=name, **options)
        created.append(f"{collection}.{name}")

    outcome = {
        "status": "APPLIED",
        "migration_version": MIGRATION_VERSION,
        "checksum": checksum(),
        "validators_applied": len(VALIDATORS),
        "collections_recreated": sorted(VALIDATORS),
        "empty_precondition_verified": True,
        "indexes_created": created,
        "business_document_writes": 0,
        "business_document_deletes": 0,
    }
    now = datetime.now(timezone.utc)
    db.schema_migrations.update_one(
        {"version": MIGRATION_VERSION},
        {
            "$set": {
                "checksum": checksum(),
                "status": "APPLIED",
                "applied_at": now,
                "result": outcome,
            },
            "$setOnInsert": {"started_at": now},
        },
        upsert=True,
    )
    return outcome


def verify(db) -> Dict[str, Any]:
    issues: List[Dict[str, str]] = []
    for collection, validator in VALIDATORS.items():
        info = db.command({"listCollections": 1, "filter": {"name": collection}})
        batch = info.get("cursor", {}).get("firstBatch", [])
        options = batch[0].get("options", {}) if batch else {}
        if options.get("validationLevel") != "strict":
            issues.append({"collection": collection, "issue": "validationLevel"})
        if options.get("validationAction") != "error":
            issues.append({"collection": collection, "issue": "validationAction"})
        if options.get("validator") != validator:
            issues.append({"collection": collection, "issue": "validator"})
    remaining = plan(db)["index_creates"]
    ledger = db.schema_migrations.find_one(
        {"version": MIGRATION_VERSION}, {"_id": 0, "status": 1, "checksum": 1}
    )
    checks = {
        "validators_match": not issues,
        "indexes_match": not remaining,
        "ledger_applied": bool(ledger and ledger.get("status") == "APPLIED"),
        "checksum_matches": bool(ledger and ledger.get("checksum") == checksum()),
    }
    return {
        "migration_version": MIGRATION_VERSION,
        "mode": "verify",
        "verification_passed": all(checks.values()),
        "checks": checks,
        "validator_issues": issues,
        "missing_indexes": remaining,
        "business_document_writes": 0,
        "business_document_deletes": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("dry-run", "apply", "recreate-empty", "verify"),
        default="dry-run",
    )
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
    if args.mode == "recreate-empty" and args.confirmation != "RECREATE_EMPTY_TREL_DB_P3":
        print(
            "Empty recreation requires --confirmation RECREATE_EMPTY_TREL_DB_P3",
            file=sys.stderr,
        )
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
            output = plan(db)
        elif args.mode == "apply":
            output = apply(db)
        elif args.mode == "recreate-empty":
            output = recreate_empty(db)
        else:
            output = verify(db)
        print(json.dumps(output, indent=2, default=str, sort_keys=True))
        return 0 if args.mode != "verify" or output["verification_passed"] else 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
