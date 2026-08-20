"""Additive P1 physical schema extension for the integrated TRELPNG database.

The migration is intentionally idempotent and does not copy, update, or delete
legacy business documents.  It creates the approved integrated collections,
validators, indexes, and migration-control ledger only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from pymongo import ASCENDING, DESCENDING, MongoClient


MIGRATION_VERSION = "2026.08.20.p1_schema_extension"
DB_NAME = "trel_db"

LEGACY_COLLECTIONS = {
    "cities", "communications", "content", "customers", "files",
    "inspections", "leads", "notifications", "page_content", "properties",
    "property_types", "provinces", "requirements", "suburbs", "users",
}

PHYSICAL_COLLECTIONS: Sequence[str] = (
    "users", "roles", "permissions", "user_roles", "staff_profiles",
    "advertiser_profiles", "referral_partner_profiles", "identity_documents",
    "verification_events", "auth_sessions", "audit_events", "provinces",
    "districts", "cities", "suburbs", "local_areas", "streets",
    "property_types", "parties", "party_contacts", "master_properties",
    "property_addresses", "property_parcels", "property_units",
    "property_attributes", "property_parties", "property_documents",
    "property_match_candidates", "advertiser_authorities", "property_drafts",
    "listings", "listing_prices", "listing_status_history", "listing_media",
    "features", "listing_features", "property_referrals",
    "referral_handover_events", "referral_commissions", "properties", "customers", "leads",
    "requirements", "requirement_locations", "property_requirement_matches",
    "inspections", "communications", "tasks", "source_sites",
    "collection_runs", "source_listings", "source_listing_observations",
    "observation_prices", "observation_status_history",
    "property_match_reviews", "guidance_requests", "guidance_subject_snapshots",
    "comparable_candidates", "guidance_results",
    "guidance_comparable_summaries", "files", "content", "page_content",
    "notifications", "schema_migrations", "migration_id_map",
    "migration_exceptions",
)


def _generic_validator() -> Dict[str, Any]:
    return {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["id"],
            "properties": {"id": {"bsonType": "string", "minLength": 1}},
        }
    }


SPECIAL_VALIDATORS: Dict[str, Dict[str, Any]] = {
    "schema_migrations": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["version", "checksum", "status", "started_at"],
            "properties": {
                "version": {"bsonType": "string"},
                "checksum": {"bsonType": "string"},
                "status": {"enum": ["RUNNING", "APPLIED", "FAILED"]},
                "started_at": {"bsonType": "date"},
                "applied_at": {"bsonType": "date"},
            },
        }
    },
    "migration_id_map": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["id", "source_collection", "source_id", "target_type", "target_id", "migration_version", "created_at"],
            "properties": {
                "id": {"bsonType": "string"},
                "source_collection": {"bsonType": "string"},
                "source_id": {"bsonType": "string"},
                "target_type": {"bsonType": "string"},
                "target_id": {"bsonType": "string"},
                "migration_version": {"bsonType": "string"},
                "created_at": {"bsonType": "date"},
            },
        }
    },
    "migration_exceptions": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["id", "migration_version", "source_collection", "source_id", "error_code", "status", "created_at"],
            "properties": {
                "id": {"bsonType": "string"},
                "migration_version": {"bsonType": "string"},
                "source_collection": {"bsonType": "string"},
                "source_id": {"bsonType": "string"},
                "error_code": {"bsonType": "string"},
                "status": {"enum": ["OPEN", "ACCEPTED", "RESOLVED"]},
                "created_at": {"bsonType": "date"},
            },
        }
    },
}


IndexSpec = Tuple[str, str, Sequence[Tuple[str, int]], Dict[str, Any]]

INDEXES: Sequence[IndexSpec] = (
    ("users", "ux_users_email", (("email", ASCENDING),), {"unique": True}),
    ("users", "ix_users_category_status", (("account_category", ASCENDING), ("status", ASCENDING)), {}),
    ("user_roles", "ux_user_roles", (("user_id", ASCENDING), ("role_id", ASCENDING)), {"unique": True}),
    ("auth_sessions", "ux_session_token", (("token_hash", ASCENDING),), {"unique": True}),
    ("auth_sessions", "ttl_session_expiry", (("expires_at", ASCENDING),), {"expireAfterSeconds": 0}),
    ("audit_events", "ix_audit_subject", (("subject_type", ASCENDING), ("subject_id", ASCENDING), ("created_at", DESCENDING)), {}),
    ("audit_events", "ix_audit_actor", (("actor_id", ASCENDING), ("created_at", DESCENDING)), {}),
    ("master_properties", "ux_master_property_id", (("id", ASCENDING),), {"unique": True}),
    ("master_properties", "ix_property_parent", (("parent_property_id", ASCENDING),), {"sparse": True}),
    ("property_addresses", "ux_canonical_address", (("property_id", ASCENDING), ("is_canonical", ASCENDING)), {"unique": True, "partialFilterExpression": {"is_canonical": True, "valid_to": None}}),
    ("property_addresses", "ix_micro_location", (("suburb_id", ASCENDING), ("local_area_id", ASCENDING), ("street_id", ASCENDING)), {}),
    ("property_parcels", "ix_urban_identity", (("province_id", ASCENDING), ("suburb_id", ASCENDING), ("street_norm", ASCENDING), ("section_norm", ASCENDING), ("lot_norm", ASCENDING)), {"partialFilterExpression": {"identifier_scheme": "URBAN_LOT_SECTION"}}),
    ("property_parcels", "ix_portion_identity", (("province_id", ASCENDING), ("district_id", ASCENDING), ("location_norm", ASCENDING), ("portion_norm", ASCENDING)), {"partialFilterExpression": {"identifier_scheme": {"$in": ["PORTION", "CUSTOMARY"]}}}),
    ("property_parties", "ix_property_owner", (("property_id", ASCENDING), ("relationship_type", ASCENDING), ("authority_status", ASCENDING)), {}),
    ("property_match_candidates", "ux_property_pair", (("property_id_low", ASCENDING), ("property_id_high", ASCENDING)), {"unique": True}),
    ("property_match_candidates", "ix_match_queue", (("status", ASCENDING), ("confidence", DESCENDING), ("created_at", ASCENDING)), {}),
    ("property_drafts", "ix_user_drafts", (("user_id", ASCENDING), ("status", ASCENDING), ("updated_at", DESCENDING)), {}),
    ("listings", "ix_public_search", (("publication_status", ASCENDING), ("transaction_type", ASCENDING), ("suburb_id", ASCENDING), ("property_type_id", ASCENDING), ("price_current", ASCENDING)), {}),
    ("listings", "ux_responsible_channel", (("property_id", ASCENDING), ("transaction_type", ASCENDING), ("responsible_channel_active", ASCENDING)), {"unique": True, "partialFilterExpression": {"responsible_channel_active": True}}),
    ("listing_prices", "ux_listing_effective_price", (("listing_id", ASCENDING), ("effective_from", ASCENDING)), {"unique": True}),
    ("listing_status_history", "ix_listing_status_time", (("listing_id", ASCENDING), ("changed_at", DESCENDING)), {}),
    ("listing_media", "ux_listing_media_order", (("listing_id", ASCENDING), ("sort_order", ASCENDING)), {"unique": True}),
    ("property_referrals", "ux_original_referral", (("property_id", ASCENDING), ("is_original_referral", ASCENDING)), {"unique": True, "partialFilterExpression": {"is_original_referral": True}}),
    ("property_referrals", "ix_partner_referrals", (("referral_partner_id", ASCENDING), ("status", ASCENDING), ("referred_at", DESCENDING)), {}),
    ("leads", "ix_lead_queue", (("status", ASCENDING), ("assigned_agent_id", ASCENDING), ("created_at", DESCENDING)), {}),
    ("requirements", "ix_requirements", (("status", ASCENDING), ("intent", ASCENDING), ("property_type_id", ASCENDING)), {}),
    ("inspections", "ix_inspection_schedule", (("assigned_staff_id", ASCENDING), ("status", ASCENDING), ("scheduled_at", ASCENDING)), {}),
    ("source_sites", "ux_source_domain", (("domain", ASCENDING),), {"unique": True}),
    ("source_listings", "ux_source_listing", (("source_site_id", ASCENDING), ("source_listing_id", ASCENDING)), {"unique": True}),
    ("source_listings", "ix_last_seen", (("current_status", ASCENDING), ("last_seen_at", ASCENDING)), {}),
    ("source_listing_observations", "ux_observation", (("source_listing_id", ASCENDING), ("observed_at", ASCENDING)), {"unique": True}),
    ("source_listing_observations", "ix_comparable_lookup", (("transaction_type", ASCENDING), ("property_type_id", ASCENDING), ("suburb_id", ASCENDING), ("local_area_id", ASCENDING), ("observed_at", DESCENDING), ("priced_usable", ASCENDING)), {"partialFilterExpression": {"priced_usable": True}}),
    ("observation_prices", "ix_monthly_price", (("monthly_equivalent", ASCENDING), ("price_per_sqm", ASCENDING)), {"sparse": True}),
    ("comparable_candidates", "ux_request_observation", (("guidance_request_id", ASCENDING), ("observation_id", ASCENDING)), {"unique": True}),
    ("guidance_results", "ux_guidance_version", (("guidance_request_id", ASCENDING), ("version", ASCENDING)), {"unique": True}),
    ("schema_migrations", "ux_migration_version", (("version", ASCENDING),), {"unique": True}),
    ("migration_id_map", "ux_migration_map", (("source_collection", ASCENDING), ("source_id", ASCENDING), ("target_type", ASCENDING)), {"unique": True}),
    ("migration_exceptions", "ix_migration_exception_queue", (("migration_version", ASCENDING), ("status", ASCENDING), ("error_code", ASCENDING)), {}),
)


def schema_checksum() -> str:
    payload = {
        "version": MIGRATION_VERSION,
        "collections": list(PHYSICAL_COLLECTIONS),
        "indexes": [
            [collection, name, list(keys), options]
            for collection, name, keys, options in INDEXES
        ],
        "special_validators": SPECIAL_VALIDATORS,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def _equivalent_index(existing: Iterable[Dict[str, Any]], keys: Sequence[Tuple[str, int]], options: Dict[str, Any]) -> bool:
    wanted_keys = list(keys)
    for item in existing:
        if list(item.get("key", {}).items()) != wanted_keys:
            continue
        if bool(item.get("unique")) != bool(options.get("unique")):
            continue
        if item.get("expireAfterSeconds") != options.get("expireAfterSeconds"):
            continue
        return True
    return False


def build_plan(db) -> Dict[str, Any]:
    existing_names = set(db.list_collection_names())
    create_collections = [name for name in PHYSICAL_COLLECTIONS if name not in existing_names]
    create_indexes: List[Dict[str, str]] = []
    skip_equivalent_indexes: List[Dict[str, str]] = []
    for collection, name, keys, options in INDEXES:
        existing = list(db[collection].list_indexes()) if collection in existing_names else []
        target = {"collection": collection, "name": name}
        if _equivalent_index(existing, keys, options):
            skip_equivalent_indexes.append(target)
        else:
            create_indexes.append(target)
    return {
        "migration_version": MIGRATION_VERSION,
        "checksum": schema_checksum(),
        "database": db.name,
        "legacy_collections_untouched": sorted(LEGACY_COLLECTIONS),
        "create_collections": create_collections,
        "create_indexes": create_indexes,
        "skip_equivalent_indexes": skip_equivalent_indexes,
    }


def apply(db) -> Dict[str, Any]:
    checksum = schema_checksum()
    existing = db.schema_migrations.find_one({"version": MIGRATION_VERSION}) if "schema_migrations" in db.list_collection_names() else None
    if existing and existing.get("status") == "APPLIED":
        if existing.get("checksum") != checksum:
            raise RuntimeError("Applied migration checksum does not match source")
        return {"status": "ALREADY_APPLIED", "version": MIGRATION_VERSION, "checksum": checksum}

    plan = build_plan(db)
    created_collections: List[str] = []
    created_indexes: List[str] = []

    for name in plan["create_collections"]:
        validator = SPECIAL_VALIDATORS.get(name, _generic_validator())
        db.create_collection(name, validator=validator, validationLevel="strict", validationAction="error")
        created_collections.append(name)

    attempt_started_at = datetime.now(timezone.utc)
    db.schema_migrations.update_one(
        {"version": MIGRATION_VERSION},
        {
            "$set": {
                "checksum": checksum,
                "status": "RUNNING",
                "last_attempt_at": attempt_started_at,
            },
            "$setOnInsert": {"started_at": attempt_started_at},
            "$unset": {"failed_at": "", "failure_code": ""},
        },
        upsert=True,
    )

    for collection, name, keys, options in INDEXES:
        existing_indexes = list(db[collection].list_indexes())
        if _equivalent_index(existing_indexes, keys, options):
            continue
        db[collection].create_index(list(keys), name=name, **options)
        created_indexes.append(f"{collection}.{name}")

    result = {
        "created_collections": created_collections,
        "created_indexes": created_indexes,
        "legacy_document_writes": 0,
    }
    db.schema_migrations.update_one(
        {"version": MIGRATION_VERSION},
        {"$set": {"status": "APPLIED", "applied_at": datetime.now(timezone.utc), "result": result}},
    )
    return {"status": "APPLIED", "version": MIGRATION_VERSION, "checksum": checksum, **result}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("dry-run", "apply"), default="dry-run")
    parser.add_argument("--uri", default=os.environ.get("MONGO_URL"))
    parser.add_argument("--username", default=os.environ.get("MONGO_USERNAME"))
    parser.add_argument("--auth-database", default=os.environ.get("MONGO_AUTH_DATABASE", "admin"))
    parser.add_argument("--database", default=os.environ.get("DB_NAME", DB_NAME))
    args = parser.parse_args()
    if not args.uri:
        print("MONGO_URL or --uri is required", file=sys.stderr)
        return 2

    client_options: Dict[str, Any] = {"serverSelectionTimeoutMS": 15000}
    password = os.environ.get("MONGO_PASSWORD")
    if args.username:
        client_options.update(
            username=args.username,
            password=password,
            authSource=args.auth_database,
        )
    client = MongoClient(args.uri, **client_options)
    try:
        db = client[args.database]
        db.command("ping")
        output = build_plan(db) if args.mode == "dry-run" else apply(db)
        print(json.dumps(output, indent=2, default=str, sort_keys=True))
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
