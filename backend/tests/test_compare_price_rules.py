from core.comparable_evidence import _score, _strength


def test_evidence_strength_thresholds():
    assert _strength(2) == "INSUFFICIENT"
    assert _strength(3) == "LIMITED"
    assert _strength(6) == "MODERATE"
    assert _strength(11) == "STRONG"


def test_all_approved_fields_improve_comparable_score():
    subject = {
        "property_type_id": "house", "suburb_id": "boroko", "local_area_id": "stage-2",
        "bedrooms": 3, "bathrooms": 2, "parking": 2,
        "land_area_sqm": 900, "building_area_sqm": 180,
        "property_condition": "GOOD", "tenure_type": "STATE_LEASE",
    }
    exact = dict(subject)
    weak = {
        **exact, "local_area_id": "stage-9", "bedrooms": 5, "bathrooms": 4,
        "parking": 0, "land_area_sqm": 300, "building_area_sqm": 60,
        "property_condition": "POOR", "tenure_type": "CUSTOMARY",
    }
    assert _score(exact, subject) > _score(weak, subject)


def test_missing_optional_values_do_not_reject_a_comparable():
    subject = {"property_type_id": "land", "suburb_id": "nine-mile", "land_area_sqm": 1200}
    incomplete = {"property_type_id": "land", "suburb_id": "nine-mile"}
    assert _score(incomplete, subject) > 0
