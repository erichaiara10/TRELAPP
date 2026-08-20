from migrations.property_backfill import (
    MIGRATION_VERSION,
    analyze,
    stable_id,
    transform,
)
from datetime import datetime, timezone


VALID = {
    "id": "legacy-property-1",
    "title": "Sample",
    "listing_type": "sale",
    "property_type": "House",
    "price": 750000,
    "currency": "PGK",
    "province": "NCD",
    "location": "Port Moresby",
    "suburb": "Waigani",
    "allotment_number": "15",
    "section_number": "42",
    "street_name": "Waigani Drive",
    "total_area_ha": 0.08,
}


def test_stable_ids_are_repeatable_and_scoped():
    assert stable_id("listing", "x") == stable_id("listing", "x")
    assert stable_id("listing", "x") != stable_id("master_property", "x")


def test_transform_builds_integrated_property_graph():
    result = transform(VALID, datetime.now(timezone.utc))
    assert set(result) == {
        "master_properties",
        "property_addresses",
        "property_parcels",
        "property_attributes",
        "listings",
        "listing_prices",
    }
    property_id = result["master_properties"]["id"]
    assert result["listings"]["property_id"] == property_id
    assert result["property_addresses"]["property_id"] == property_id
    assert result["property_addresses"]["valid_to"] is None
    assert result["property_parcels"]["identifier_scheme"] == "URBAN_LOT_SECTION"
    assert result["listings"]["transaction_type"] == "SALE"


def test_dry_run_counts_valid_and_exception_records_without_writes():
    invalid = {**VALID, "id": "bad", "price": 0}
    result = analyze([VALID, invalid])
    assert result["migration_version"] == MIGRATION_VERSION
    assert result["source_documents"] == 2
    assert result["valid_source_documents"] == 1
    assert result["exception_documents"] == 1
    assert result["exception_codes"] == {"PRICE_INVALID": 1}
    assert result["planned_upserts"]["master_properties"] == 1
    assert result["planned_upserts"]["migration_id_map"] == 2
    assert result["legacy_document_writes"] == 0
    assert result["legacy_document_deletes"] == 0
