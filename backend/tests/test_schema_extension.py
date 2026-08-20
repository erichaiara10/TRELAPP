from migrations.schema_extension import (
    INDEXES,
    LEGACY_COLLECTIONS,
    MIGRATION_VERSION,
    PHYSICAL_COLLECTIONS,
    SPECIAL_VALIDATORS,
    schema_checksum,
)


def test_schema_plan_is_stable_and_unique():
    assert MIGRATION_VERSION == "2026.08.20.p1_schema_extension"
    assert len(PHYSICAL_COLLECTIONS) == len(set(PHYSICAL_COLLECTIONS))
    assert len(PHYSICAL_COLLECTIONS) == 67
    assert len(INDEXES) == 38
    assert len(schema_checksum()) == 64


def test_legacy_collections_are_retained_in_physical_plan():
    assert LEGACY_COLLECTIONS.issubset(set(PHYSICAL_COLLECTIONS))


def test_control_collections_have_specific_validators():
    assert set(SPECIAL_VALIDATORS) == {
        "schema_migrations",
        "migration_id_map",
        "migration_exceptions",
    }


def test_canonical_address_partial_index_is_atlas_compatible():
    spec = next(item for item in INDEXES if item[1] == "ux_canonical_address")
    assert spec[3]["partialFilterExpression"] == {
        "is_canonical": True,
        "valid_to": None,
    }
