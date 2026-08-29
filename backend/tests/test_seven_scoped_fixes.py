"""Focused regression tests for the seven scoped property-listing fixes."""
import pytest
from pydantic import ValidationError

from models import InspectionCreate, LeadCreate
from routes.staff_property_advertising import property_reference_counter_key


def test_property_reference_uses_advertiser_prefix_and_publication_year():
    assert property_reference_counter_key("Advertise only", "2027-01-01T00:00:00Z") == "A27"


def test_property_reference_uses_trel_prefix_and_dynamic_year():
    assert property_reference_counter_key("TREL to sell/manage", "2028-06-15T10:00:00+10:00") == "T28"


def test_inspection_requires_a_saved_iso_preferred_date():
    with pytest.raises(ValidationError):
        InspectionCreate(property_id="property-1", customer_name="Jane Doe")
    request = InspectionCreate(
        property_id="property-1",
        customer_name="Jane Doe",
        preferred_date="2027-01-02",
    )
    assert request.preferred_date == "2027-01-02"


@pytest.mark.parametrize("model,payload", [
    (LeadCreate, {"source": "property_enquiry", "name": "Jane123"}),
    (InspectionCreate, {
        "property_id": "property-1",
        "customer_name": "Jane123",
        "preferred_date": "2027-01-02",
    }),
])
def test_public_names_reject_invalid_characters(model, payload):
    with pytest.raises(ValidationError):
        model(**payload)
