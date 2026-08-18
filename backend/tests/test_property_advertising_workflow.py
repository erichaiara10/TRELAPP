"""Pure contract tests for the S-series workflow definition."""
import pytest

from fastapi import HTTPException

from routes.property_advertising import (
    SEED, STATUS_INDEX, TRANSITIONS, WorkflowAction,
    require_advertiser, validate_submission,
)


def test_every_seed_row_has_unique_reference_and_status_slot():
    type_for_key = {
        "advertisers": "advertiser", "submissions": "submission",
        "publications": "publication", "location_requests": "location_request",
        "lifecycle": "lifecycle",
    }
    for key, rows in SEED.items():
        assert len({row[0] for row in rows}) == len(rows)
        status_index = STATUS_INDEX[type_for_key[key]]
        assert all(len(row) > status_index and row[status_index] for row in rows)


def test_every_record_type_has_declared_actions():
    assert set(STATUS_INDEX) == set(TRANSITIONS)
    assert all(actions for actions in TRANSITIONS.values())


def test_workflow_action_rejects_unknown_record_type():
    with pytest.raises(ValueError):
        WorkflowAction(record_type="operations", reference="O-1", action="publish")


def test_workflow_action_validates_reference_and_action():
    with pytest.raises(ValueError):
        WorkflowAction(record_type="publication", reference="x", action="publish")
    with pytest.raises(ValueError):
        WorkflowAction(record_type="publication", reference="LIST-1", action="x")


def test_submission_validation_contract():
    valid = {
        "listing_type": "Sale", "service": "Advertise only",
        "relationship": "Owner / Joint Owner", "property_class": "Residential",
        "property_type": "House", "title": "Test House", "price": "950,000",
        "description": "A complete test property", "province": "NCD",
        "city": "Port Moresby", "suburb": "Boroko", "section": "54", "lot": "12",
        "authority_confirmed": True, "terms_accepted": True,
    }
    validate_submission(valid)
    with pytest.raises(HTTPException) as missing:
        validate_submission({**valid, "section": ""})
    assert missing.value.status_code == 400
    with pytest.raises(HTTPException) as declaration:
        validate_submission({**valid, "terms_accepted": False})
    assert declaration.value.status_code == 400


def test_advertiser_role_guard():
    require_advertiser({"role": "property_advertiser"})
    with pytest.raises(HTTPException) as forbidden:
        require_advertiser({"role": "sales_agent"})
    assert forbidden.value.status_code == 403
