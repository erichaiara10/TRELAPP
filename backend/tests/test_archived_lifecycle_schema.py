from migrations.p3_integrated_property import VALIDATORS


def test_master_property_lifecycle_accepts_archived():
    lifecycle = (
        VALIDATORS["master_properties"]["$jsonSchema"]["properties"]["lifecycle_status"]
    )

    assert "archived" in lifecycle["enum"]
