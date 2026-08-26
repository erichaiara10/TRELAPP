from core.property_advertising_rules import (
    add_business_days,
    advertiser_display_status,
    content_blockers,
    duplicate_identity_match,
    lifecycle_deadlines,
    lifecycle_action_allowed,
    lifecycle_filter_match,
    lifecycle_transition,
    optional_number,
    price_label,
    public_listing_visible,
    publication_transition,
    submission_sla,
)
from datetime import datetime, timezone


def _complete(**changes):
    data = {
        "title": "Family house", "description": "Complete public description",
        "listing_type": "Sale", "property_class": "Residential", "property_type": "House",
        "province": "NCD", "service": "Advertise only", "relationship": "Owner / Joint Owner",
        "identity_scheme": "SERVICED", "lot": "15", "section": "42", "city": "Port Moresby",
        "currency": "PGK", "price": 500000,
        "photos": [{"url": "/a.jpg", "type": "image/jpeg", "size": 1000},
                   {"url": "/b.png", "type": "image/png", "size": 2000}],
        "authority_confirmed": True, "terms_accepted": True,
    }
    data.update(changes)
    return data


def test_serviced_duplicate_requires_allotment_section_and_one_locality():
    original = {"lot": "15", "section": "42", "city": "Port Moresby"}
    assert duplicate_identity_match(original, {"allotment_number": " 15 ", "section_number": "42", "town": "PORT MORESBY"})
    assert not duplicate_identity_match(original, {"allotment_number": "15", "section_number": "41", "town": "Port Moresby"})
    assert not duplicate_identity_match(original, {"allotment_number": "15", "section_number": "42", "town": "Lae"})


def test_serviced_locality_can_be_street_or_suburb():
    assert duplicate_identity_match(
        {"lot": "8", "section": "3", "street": "Waigani Drive"},
        {"lot": "8", "section": "3", "street_name": "waigani drive"},
    )
    assert duplicate_identity_match(
        {"lot": "8", "section": "3", "suburb": "Boroko"},
        {"lot": "8", "section": "3", "suburb": "BOROKO"},
    )


def test_large_portion_duplicate_requires_portion_and_location_or_town():
    original = {"identity_scheme": "LARGE_PORTION", "portion": "2145C", "location": "Hula"}
    assert duplicate_identity_match(original, {"full_portion_number": "2145c", "city": "HULA"})
    assert not duplicate_identity_match(original, {"full_portion_number": "2145B", "city": "Hula"})
    assert not duplicate_identity_match(original, {"full_portion_number": "2145C", "city": "Lae"})


def test_publication_content_requires_two_valid_photos():
    blockers = content_blockers(_complete(photos=[{"url": "/one.jpg", "type": "image/jpeg", "size": 1000}]))
    assert "At least 2 valid property photos are required" in blockers
    assert content_blockers(_complete()) == []


def test_negotiable_and_contact_price_do_not_display_amount():
    assert content_blockers(_complete(currency="Negotiable", price="")) == []
    assert price_label({"currency": "Negotiable", "price": 1000}) == "Negotiable"
    assert price_label({"currency": "Contact for price", "price": 1000}) == "Contact for Price"


def test_publication_and_lifecycle_transitions_reject_invalid_jumps():
    assert publication_transition("DRAFT", "PUBLISH") == "PUBLISHED"
    assert publication_transition("DRAFT", "SUSPEND") is None
    assert publication_transition("PUBLISHED", "SUSPEND") == "SUSPENDED"
    assert lifecycle_transition("CURRENT", "ARCHIVE") == "ARCHIVED"
    assert lifecycle_transition("ARCHIVED", "SEND_CONFIRMATION") is None


def test_closed_listing_can_only_be_archived_after_unpublishing():
    assert lifecycle_action_allowed("CURRENT", "ARCHIVE", "SOLD", "UNPUBLISHED")
    assert lifecycle_action_allowed("CURRENT", "ARCHIVE", "LEASED", "UNPUBLISHED")
    assert lifecycle_action_allowed("CURRENT", "ARCHIVE", "WITHDRAWN", "UNPUBLISHED")
    assert not lifecycle_action_allowed("CURRENT", "ARCHIVE", "SOLD", "PUBLISHED")
    assert not lifecycle_action_allowed("CURRENT", "SEND_CONFIRMATION", "SOLD", "UNPUBLISHED")
    assert not lifecycle_action_allowed("CURRENT", "SUSPEND", "SOLD", "UNPUBLISHED")
    assert not lifecycle_action_allowed("ARCHIVED", "REACTIVATE", "SOLD", "UNPUBLISHED")


def test_lifecycle_filters_keep_outcome_separate_from_record_status():
    sold_archive = {"availability": "SOLD", "lifecycle_status": "ARCHIVED"}
    legacy_archive = {"availability": "ARCHIVED", "lifecycle_status": "ARCHIVED"}
    assert lifecycle_filter_match(sold_archive, "SOLD")
    assert lifecycle_filter_match(sold_archive, "ARCHIVED")
    assert not lifecycle_filter_match(legacy_archive, "SOLD")
    assert lifecycle_filter_match(legacy_archive, "ARCHIVED")


def test_public_visibility_requires_published_and_live():
    assert public_listing_visible("PUBLISHED", "AVAILABLE")
    assert not public_listing_visible("SUSPENDED", "AVAILABLE")
    assert not public_listing_visible("PUBLISHED", "SOLD")


def test_advertiser_display_status_uses_real_workflow_state():
    assert advertiser_display_status("UNDER_REVIEW") == "Under Review"
    assert advertiser_display_status("APPROVED", "PUBLISHED", "AVAILABLE") == "Live"
    assert advertiser_display_status("APPROVED", "UNPUBLISHED", "SUSPENDED") == "Inactive"
    assert advertiser_display_status("APPROVED", "PUBLISHED", "SOLD") == "Sold"
    assert advertiser_display_status("DRAFT") == "Draft"


def test_submission_sla_counts_three_business_days():
    submitted = datetime(2026, 8, 21, 9, 0, tzinfo=timezone.utc)  # Friday
    due = add_business_days(submitted, 3)
    assert due.date().isoformat() == "2026-08-26"
    assert submission_sla(submitted, "UNDER_REVIEW", now=datetime(2026, 8, 25, tzinfo=timezone.utc))[1] == "ON TRACK"
    assert submission_sla(submitted, "UNDER_REVIEW", now=due.replace(hour=23))[1] == "DUE TODAY"
    assert submission_sla(submitted, "APPROVED", now=due)[1] == "COMPLETED"


def test_lifecycle_deadlines_handle_month_end():
    deadlines = lifecycle_deadlines("2026-01-31T00:00:00+00:00")
    assert deadlines["next_due"].startswith("2026-04-30")
    assert deadlines["unpublish_due"].startswith("2026-07-31")
    assert deadlines["archive_due"].startswith("2027-01-31")


def test_optional_number_converts_form_values_for_storage():
    assert optional_number(" 180.5 ") == 180.5
    assert optional_number("600") == 600.0
    assert optional_number(42) == 42.0
    assert optional_number("") is None
    lifecycle_deadlines,
