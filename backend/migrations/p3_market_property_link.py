"""Additive schema hardening for the market-evidence to Master Property link."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone

from pymongo import ASCENDING, DESCENDING, MongoClient

MIGRATION_VERSION = "2026.08.20.p3_market_property_link"
CONFIRMATION = "APPLY_TREL_DB_P3_MARKET_LINK"
DB_NAME = "trel_db"

STRING = {"bsonType": "string", "minLength": 1}
NULLABLE_STRING = {"bsonType": ["string", "null"]}
NUMBER = {"bsonType": ["double", "int", "long", "decimal"]}
NULLABLE_NUMBER = {"bsonType": ["double", "int", "long", "decimal", "null"]}


def schema(required, properties):
    return {"$jsonSchema": {"bsonType": "object", "required": required, "properties": properties}}


VALIDATORS = {
    "source_sites": schema(
        ["id", "name", "domain", "active", "is_trel_owned", "created_at", "updated_at"],
        {"id": STRING, "name": STRING, "domain": STRING, "base_url": NULLABLE_STRING,
         "active": {"bsonType": "bool"}, "is_trel_owned": {"bsonType": "bool"},
         "created_at": STRING, "updated_at": STRING},
    ),
    "source_listings": schema(
        ["id", "source_site_id", "source_listing_id", "source_url", "match_status",
         "origin_kind", "current_status", "transaction_type", "first_seen_at", "last_seen_at", "last_checked_at", "created_at", "updated_at"],
        {"id": STRING, "source_site_id": STRING, "source_listing_id": STRING, "source_url": STRING,
         "master_property_id": NULLABLE_STRING,
         "match_status": {"enum": ["MATCHED", "REVIEW_REQUIRED", "UNMATCHED"]},
         "match_confidence": NUMBER, "match_rule": NULLABLE_STRING,
         "origin_kind": {"enum": ["EXTERNAL", "TREL_OWN"]},
         "current_status": {"enum": ["ACTIVE", "NOT_SEEN", "REMOVED", "RELISTED", "SOLD_CONFIRMED", "RENTED_CONFIRMED", "WITHDRAWN_CONFIRMED", "UNKNOWN"]},
         "transaction_type": {"enum": ["SALE", "RENT"]},
         "first_seen_at": STRING, "last_seen_at": STRING, "last_checked_at": STRING, "created_at": STRING, "updated_at": STRING},
    ),
    "source_listing_observations": schema(
        ["id", "source_listing_id", "observed_at", "status", "transaction_type", "priced_usable", "comparable_eligible", "created_at"],
        {"id": STRING, "source_listing_id": STRING, "observed_at": STRING,
         "status": {"enum": ["ACTIVE", "NOT_SEEN", "REMOVED", "RELISTED", "SOLD_CONFIRMED", "RENTED_CONFIRMED", "WITHDRAWN_CONFIRMED", "UNKNOWN"]},
         "transaction_type": {"enum": ["SALE", "RENT"]},
         "property_type_id": NULLABLE_STRING, "province_id": NULLABLE_STRING,
         "suburb_id": NULLABLE_STRING, "local_area_id": NULLABLE_STRING,
         "priced_usable": {"bsonType": "bool"}, "comparable_eligible": {"bsonType": "bool"},
         "created_at": STRING},
    ),
    "observation_prices": schema(
        ["id", "observation_id", "amount", "currency", "price_type", "created_at"],
        {"id": STRING, "observation_id": STRING, "amount": NUMBER, "currency": {"enum": ["PGK"]},
         "price_type": {"enum": ["FIXED", "NEGOTIABLE", "FROM", "RANGE", "POA", "TENDER", "EOI", "AUCTION", "UNKNOWN"]},
         "rental_period": {"enum": ["DAY", "WEEK", "FORTNIGHT", "MONTH", "YEAR", None]},
         "monthly_equivalent": NULLABLE_NUMBER, "created_at": STRING},
    ),
    "property_match_reviews": schema(
        ["id", "source_listing_id", "candidate_property_ids", "status", "created_at", "updated_at"],
        {"id": STRING, "source_listing_id": STRING, "candidate_property_ids": {"bsonType": "array", "items": STRING},
         "status": {"enum": ["OPEN", "MATCHED", "REJECTED"]}, "created_at": STRING, "updated_at": STRING},
    ),
    "collection_runs": schema(
        ["id", "source_site_id", "status", "started_at", "records_seen", "records_ingested", "records_matched", "records_review_required", "created_by"],
        {"id": STRING, "source_site_id": STRING, "status": {"enum": ["RUNNING", "SUCCESS", "FAILED"]},
         "started_at": STRING, "finished_at": NULLABLE_STRING, "records_seen": NUMBER,
         "records_ingested": NUMBER, "records_matched": NUMBER, "records_review_required": NUMBER,
         "created_by": STRING, "error": NULLABLE_STRING},
    ),
}

INDEXES = (
    ("source_listings", "ix_source_master_link", (("master_property_id", ASCENDING), ("match_status", ASCENDING)), {"sparse": True}),
    ("source_listing_observations", "ix_subject_comparables", (("transaction_type", ASCENDING), ("property_type_id", ASCENDING), ("suburb_id", ASCENDING), ("local_area_id", ASCENDING), ("observed_at", DESCENDING)), {"partialFilterExpression": {"priced_usable": True, "comparable_eligible": True}}),
    ("observation_prices", "ux_observation_price", (("observation_id", ASCENDING),), {"unique": True}),
    ("property_match_reviews", "ix_source_match_review", (("source_listing_id", ASCENDING), ("status", ASCENDING), ("created_at", DESCENDING)), {}),
    ("collection_runs", "ix_source_run_history", (("source_site_id", ASCENDING), ("started_at", DESCENDING)), {}),
)


def checksum():
    return hashlib.sha256(json.dumps({"validators": VALIDATORS, "indexes": INDEXES}, sort_keys=True, default=str).encode()).hexdigest()


def plan(db):
    names = set(db.list_collection_names())
    return {"migration_version": MIGRATION_VERSION, "checksum": checksum(), "mode": "dry-run",
            "missing_collections": sorted(set(VALIDATORS) - names),
            "validator_updates": sorted(VALIDATORS),
            "index_creates": [f"{c}.{n}" for c, n, _, _ in INDEXES]}


def apply(db):
    result = plan(db)
    if result["missing_collections"]:
        raise RuntimeError("P1 collections missing: " + ", ".join(result["missing_collections"]))
    existing = db.schema_migrations.find_one({"version": MIGRATION_VERSION})
    if existing and existing.get("status") == "APPLIED":
        if existing.get("checksum") != checksum():
            raise RuntimeError("Applied market-link checksum differs from source")
        return {"status": "ALREADY_APPLIED", **result}
    for collection, validator in VALIDATORS.items():
        db.command({"collMod": collection, "validator": validator, "validationLevel": "strict", "validationAction": "error"})
    created = []
    for collection, name, keys, options in INDEXES:
        existing_names = {item["name"] for item in db[collection].list_indexes()}
        if name not in existing_names:
            db[collection].create_index(list(keys), name=name, **options)
            created.append(f"{collection}.{name}")
    applied_at = datetime.now(timezone.utc)
    db.schema_migrations.update_one({"version": MIGRATION_VERSION}, {"$set": {
        "checksum": checksum(), "status": "APPLIED", "started_at": applied_at,
        "applied_at": applied_at, "created_indexes": created,
    }}, upsert=True)
    return {"status": "APPLIED", "created_indexes": created, **result}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("dry-run", "apply"), default="dry-run")
    parser.add_argument("--confirmation")
    args = parser.parse_args()
    client = MongoClient(
        os.environ["MONGO_URL"], username=os.getenv("MONGO_USERNAME"), password=os.getenv("MONGO_PASSWORD"),
        authSource=os.getenv("MONGO_AUTH_DATABASE", "admin"), serverSelectionTimeoutMS=10000,
    )
    db = client[os.getenv("DB_NAME", DB_NAME)]
    if args.mode == "apply":
        if args.confirmation != CONFIRMATION:
            raise SystemExit(f"Apply requires --confirmation {CONFIRMATION}")
        result = apply(db)
    else:
        result = plan(db)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
