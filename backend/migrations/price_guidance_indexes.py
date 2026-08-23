"""Additive indexes for the dual-source Compare Price query path."""
import argparse
import os

from pymongo import ASCENDING, DESCENDING, MongoClient


INDEXES = (
    ("master_properties", "ix_price_guidance_type", [("property_type_id", ASCENDING), ("lifecycle_status", ASCENDING), ("id", ASCENDING)], {}),
    ("property_addresses", "ix_price_guidance_suburb", [("suburb_id", ASCENDING), ("is_canonical", ASCENDING), ("valid_to", ASCENDING), ("property_id", ASCENDING)], {}),
    ("property_addresses", "ix_price_guidance_city", [("city_id", ASCENDING), ("is_canonical", ASCENDING), ("valid_to", ASCENDING), ("property_id", ASCENDING)], {}),
    ("property_addresses", "ix_price_guidance_local_area", [("local_area_id", ASCENDING), ("is_canonical", ASCENDING), ("valid_to", ASCENDING), ("property_id", ASCENDING)], {}),
    ("listings", "ix_price_guidance_internal", [("transaction_type", ASCENDING), ("publication_status", ASCENDING), ("property_id", ASCENDING), ("created_at", DESCENDING)], {}),
    ("source_listing_observations", "ix_price_guidance_external_names", [("transaction_type", ASCENDING), ("property_type_name", ASCENDING), ("suburb_name", ASCENDING), ("observed_at", DESCENDING)], {"partialFilterExpression": {"priced_usable": True, "comparable_eligible": True}}),
    ("source_listing_observations", "ix_price_guidance_external_local_area", [("transaction_type", ASCENDING), ("property_type_id", ASCENDING), ("local_area_id", ASCENDING), ("observed_at", DESCENDING)], {"partialFilterExpression": {"priced_usable": True, "comparable_eligible": True}}),
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("dry-run", "apply"), default="dry-run")
    parser.add_argument("--confirmation")
    args = parser.parse_args()
    client = MongoClient(os.environ["MONGO_URL"])
    database = client[os.getenv("DB_NAME", "trel_test")]
    if args.mode == "dry-run":
        print({"database": database.name, "indexes": [f"{c}.{n}" for c, n, _, _ in INDEXES], "writes": 0})
        return
    if args.confirmation != "APPLY_TREL_PRICE_GUIDANCE_INDEXES":
        raise SystemExit("Apply requires --confirmation APPLY_TREL_PRICE_GUIDANCE_INDEXES")
    for collection, name, keys, options in INDEXES:
        database[collection].create_index(keys, name=name, **options)
    print({"database": database.name, "status": "APPLIED", "indexes": len(INDEXES), "document_writes": 0})


if __name__ == "__main__":
    main()
