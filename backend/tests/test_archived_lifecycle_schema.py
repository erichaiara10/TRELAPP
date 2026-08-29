from migrations.p3_integrated_property import VALIDATORS


def test_master_property_lifecycle_uses_terminal_business_statuses():
    lifecycle = (
        VALIDATORS["master_properties"]["$jsonSchema"]["properties"]["lifecycle_status"]
    )

    assert {"sold", "leased", "withdrawn"}.issubset(lifecycle["enum"])
    assert "archived" not in lifecycle["enum"]
