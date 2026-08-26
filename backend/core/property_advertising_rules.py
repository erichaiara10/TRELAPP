"""Authoritative business rules for Property Advertising workflows.

The functions in this module are intentionally side-effect free.  Advertiser,
Staff and public routes all use the same validation and transition rules so a
browser cannot bypass them by calling an endpoint directly.
"""
from __future__ import annotations

import re
import calendar
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional


MIN_PROPERTY_PHOTOS = 2
MAX_PROPERTY_PHOTOS = 7
MAX_PROPERTY_PHOTO_BYTES = 5 * 1024 * 1024
VALID_PROPERTY_PHOTO_TYPES = {"image/jpeg", "image/png"}

PROPERTY_CLASS_TYPES = {
    "RESIDENTIAL": {"HOUSE", "APARTMENT / UNIT", "TOWNHOUSE", "LAND"},
    "COMMERCIAL": {"OFFICE SPACE", "RETAIL", "COMMERCIAL BUILDING", "HOTEL / LODGE"},
    "INDUSTRIAL": {"WAREHOUSE", "FACTORY", "WORKSHOP"},
    "AGRICULTURAL / RURAL": {"FARM", "PLANTATION", "RURAL LAND"},
    "VACANT LAND": {"RESIDENTIAL LAND", "COMMERCIAL LAND", "INDUSTRIAL LAND"},
    "OTHER": {"OTHER"},
}

PUBLICATION_TRANSITIONS = {
    "DRAFT": {"PUBLISH": "PUBLISHED", "RETURN": "CHANGES_REQUIRED"},
    "CHANGES_REQUIRED": {"PUBLISH": "PUBLISHED", "RETURN": "CHANGES_REQUIRED"},
    "PUBLISHED": {"SUSPEND": "SUSPENDED", "UNPUBLISH": "UNPUBLISHED"},
    "SUSPENDED": {"PUBLISH": "PUBLISHED", "UNPUBLISH": "UNPUBLISHED"},
    "UNPUBLISHED": {"PUBLISH": "PUBLISHED", "RETURN": "CHANGES_REQUIRED"},
}

LIFECYCLE_TRANSITIONS = {
    "CURRENT": {"SEND_CONFIRMATION": "AWAITING_ADVERTISER", "SUSPEND": "SUSPENDED", "ARCHIVE": "ARCHIVED"},
    "AWAITING_ADVERTISER": {"RECORD_RESPONSE": "CURRENT", "SUSPEND": "SUSPENDED", "ARCHIVE": "ARCHIVED"},
    "SUSPENDED": {"REACTIVATE": "CURRENT", "ARCHIVE": "ARCHIVED"},
    "ARCHIVED": {},
}

CLOSED_LISTING_OUTCOMES = {"SOLD", "LEASED", "WITHDRAWN"}


def lifecycle_action_allowed(workflow_status: Any, action: Any, availability: Any,
                             publication_status: Any) -> bool:
    """Apply outcome and publication guards before a lifecycle transition."""
    workflow = status_token(workflow_status) or "CURRENT"
    requested = status_token(action)
    outcome = status_token(availability)
    publication = status_token(publication_status)
    if workflow == "ARCHIVED":
        return False
    if outcome in CLOSED_LISTING_OUTCOMES:
        return requested == "ARCHIVE" and publication == "UNPUBLISHED"
    if requested == "ARCHIVE":
        return False
    return lifecycle_transition(workflow, requested) is not None


def lifecycle_filter_match(item: dict, token: Any) -> bool:
    """Keep completed-property outcome separate from lifecycle record status."""
    selected = status_token(token)
    if selected in {"SOLD", "LEASED", "WITHDRAWN"}:
        return status_token(item.get("availability")) == selected
    return status_token(item.get("lifecycle_status")) == selected


def norm(value: Any) -> str:
    """Normalize user-entered identity values for deterministic matching."""
    return re.sub(r"\s+", " ", str(value or "").strip()).upper()


def status_token(value: Any) -> str:
    return re.sub(r"[\s-]+", "_", norm(value))


def optional_number(value: Any) -> Optional[float]:
    """Convert an optional browser-form value to a database-safe number."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    return float(value)


def advertiser_display_status(submission_status: Any, publication_status: Any = None,
                              lifecycle_status: Any = None) -> str:
    """Return the single advertiser-facing state used by lists and statistics."""
    lifecycle = status_token(lifecycle_status)
    publication = status_token(publication_status)
    submission = status_token(submission_status)
    if lifecycle in {"WITHDRAWN", "SOLD", "LEASED", "ARCHIVED", "INACTIVE"}:
        return lifecycle.replace("_", " ").title()
    if lifecycle == "REACTIVATION_REQUESTED":
        return "Under Review"
    if publication in {"SUSPENDED", "UNPUBLISHED"} or lifecycle == "SUSPENDED":
        return "Inactive"
    if publication == "PUBLISHED" or lifecycle in {"LIVE", "AVAILABLE"}:
        return "Live"
    if submission == "DRAFT":
        return "Draft"
    if submission in {"UNDER_REVIEW", "SUBMITTED", "ON_HOLD", "INFORMATION_REQUIRED",
                      "CHANGES_REQUIRED", "RETURNED", "REOPENED"}:
        return "Under Review"
    if submission == "APPROVED":
        return "Approved"
    if submission == "REJECTED":
        return "Inactive"
    return "Under Review"


def parse_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def add_business_days(value: Any, days: int = 3) -> Optional[datetime]:
    current = parse_datetime(value)
    if not current:
        return None
    added = 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() < 5:
            added += 1
    return current


def add_months(value: datetime, months: int) -> datetime:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def lifecycle_deadlines(value: Any) -> dict[str, str]:
    base = parse_datetime(value) or datetime.now(timezone.utc)
    return {
        "last_confirmed": base.isoformat(),
        "next_due": add_months(base, 3).isoformat(),
        "reminder_until": add_months(base, 5).isoformat(),
        "unpublish_due": add_months(base, 6).isoformat(),
        "archive_due": add_months(base, 12).isoformat(),
    }


def submission_sla(submitted_at: Any, status: Any, *, now: Optional[datetime] = None) -> tuple[Optional[str], str]:
    due = add_business_days(submitted_at)
    if not due:
        return None, "NOT CALCULATED"
    if status_token(status) in {"APPROVED", "REJECTED"}:
        return due.isoformat(), "COMPLETED"
    current = now or datetime.now(timezone.utc)
    if current.date() == due.date():
        return due.isoformat(), "DUE TODAY"
    if current > due:
        return due.isoformat(), "OVERDUE"
    return due.isoformat(), "ON TRACK"


def first(data: dict, *keys: str) -> Any:
    for key in keys:
        value = data.get(key)
        if value is not None and str(value).strip() != "":
            return value
    return None


def identity_scheme(data: dict) -> str:
    explicit = status_token(first(data, "identity_scheme", "land_identity_type"))
    if explicit in {"LARGE_PORTION", "PORTION", "CUSTOMARY"}:
        return "LARGE_PORTION"
    if first(data, "portion", "portion_number", "full_portion_number"):
        return "LARGE_PORTION"
    return "SERVICED"


def identity_values(data: dict) -> dict[str, Any]:
    scheme = identity_scheme(data)
    if scheme == "LARGE_PORTION":
        return {
            "scheme": scheme,
            "portion": norm(first(data, "portion", "portion_number", "full_portion_number")),
            "localities": {
                value for value in (
                    norm(first(data, "location")),
                    norm(first(data, "town")),
                    norm(first(data, "city")),
                ) if value
            },
        }
    return {
        "scheme": scheme,
        "allotment": norm(first(data, "lot", "allotment_number")),
        "section": norm(first(data, "section", "section_number")),
        "localities": {
            value for value in (
                norm(first(data, "town")),
                norm(first(data, "city")),
                norm(first(data, "suburb")),
                norm(first(data, "street", "street_name")),
            ) if value
        },
    }


def identity_blockers(data: dict) -> list[str]:
    identity = identity_values(data)
    if identity["scheme"] == "LARGE_PORTION":
        blockers = []
        if not identity["portion"]:
            blockers.append("Portion number is required")
        if not identity["localities"]:
            blockers.append("Location or town is required")
        return blockers
    blockers = []
    if not identity["allotment"]:
        blockers.append("Allotment number is required")
    if not identity["section"]:
        blockers.append("Section number is required")
    if not identity["localities"]:
        blockers.append("Town, suburb or street is required")
    return blockers


def duplicate_identity_match(left: dict, right: dict) -> bool:
    """Apply the approved exact duplicate identity rules."""
    a, b = identity_values(left), identity_values(right)
    if a["scheme"] != b["scheme"]:
        return False
    if a["scheme"] == "LARGE_PORTION":
        return bool(a["portion"] and a["portion"] == b["portion"] and a["localities"] & b["localities"])
    return bool(
        a["allotment"] and a["allotment"] == b["allotment"]
        and a["section"] and a["section"] == b["section"]
        and a["localities"] & b["localities"]
    )


def identity_reasons(data: dict) -> list[str]:
    identity = identity_values(data)
    if identity["scheme"] == "LARGE_PORTION":
        return ["same portion number", "matching location or town"]
    return ["same allotment number", "same section number", "matching town, suburb or street"]


def valid_photos(data: dict) -> list[Any]:
    valid = []
    for photo in data.get("photos") or []:
        if isinstance(photo, str):
            if photo.strip():
                valid.append(photo)
            continue
        if not isinstance(photo, dict) or not str(photo.get("url") or "").strip():
            continue
        content_type = norm(photo.get("type") or photo.get("content_type")).lower()
        size = photo.get("size")
        if content_type and content_type not in VALID_PROPERTY_PHOTO_TYPES:
            continue
        if size is not None:
            try:
                if int(size) > MAX_PROPERTY_PHOTO_BYTES:
                    continue
            except (TypeError, ValueError):
                continue
        if status_token(photo.get("status")) in {"REJECTED", "FAILED", "QUARANTINED"}:
            continue
        valid.append(photo)
    return valid


def price_blockers(data: dict) -> list[str]:
    price_type = status_token(first(data, "price_type", "currency") or "PGK")
    if price_type in {"NEGOTIABLE", "CONTACT_FOR_PRICE"}:
        return []
    if price_type != "PGK":
        return ["Select PGK, Negotiable or Contact for Price"]
    try:
        if float(data.get("price") or 0) <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return ["A current PGK price greater than zero is required"]
    return []


def price_label(data: dict) -> str:
    price_type = status_token(first(data, "price_type", "currency") or "PGK")
    if price_type == "NEGOTIABLE":
        return "Negotiable"
    if price_type == "CONTACT_FOR_PRICE":
        return "Contact for Price"
    amount = data.get("price")
    return f"PGK {amount}" if amount not in {None, ""} else "PGK —"


def content_blockers(data: dict, *, require_photos: bool = True) -> list[str]:
    blockers = []
    for key, label in (
        ("title", "Property title is required"),
        ("description", "Property description is required"),
        ("listing_type", "Sale or rent must be selected"),
        ("property_class", "Property class is required"),
        ("property_type", "Property type is required"),
        ("province", "Province is required"),
        ("service", "TREL service option is required"),
        ("relationship", "Relationship to the property is required"),
    ):
        if not str(data.get(key) or "").strip():
            blockers.append(label)
    listing_type = norm(data.get("listing_type"))
    if listing_type and listing_type not in {"SALE", "RENT"}:
        blockers.append("Listing type must be Sale or Rent")
    property_class = norm(data.get("property_class"))
    property_type = norm(data.get("property_type"))
    allowed = PROPERTY_CLASS_TYPES.get(property_class)
    if property_class and property_type and allowed is not None and property_type not in allowed:
        blockers.append("Property type does not belong to the selected property class")
    blockers.extend(identity_blockers(data))
    blockers.extend(price_blockers(data))
    if require_photos:
        count = len(valid_photos(data))
        if count < MIN_PROPERTY_PHOTOS:
            blockers.append(f"At least {MIN_PROPERTY_PHOTOS} valid property photos are required")
        if len(data.get("photos") or []) > MAX_PROPERTY_PHOTOS:
            blockers.append(f"No more than {MAX_PROPERTY_PHOTOS} property photos are allowed")
    if not data.get("authority_confirmed"):
        blockers.append("Advertiser authority declaration is required")
    if not data.get("terms_accepted"):
        blockers.append("Terms of Use must be accepted")
    return blockers


def publication_transition(current: Any, action: Any) -> Optional[str]:
    return PUBLICATION_TRANSITIONS.get(status_token(current) or "DRAFT", {}).get(status_token(action))


def lifecycle_transition(current: Any, action: Any) -> Optional[str]:
    return LIFECYCLE_TRANSITIONS.get(status_token(current) or "CURRENT", {}).get(status_token(action))


def public_listing_visible(publication_status: Any, availability: Any) -> bool:
    return status_token(publication_status) == "PUBLISHED" and status_token(availability or "AVAILABLE") in {"AVAILABLE", "LIVE", "ACTIVE"}


def normalize_candidates(candidates: Iterable[dict]) -> list[dict]:
    """De-duplicate candidate results while retaining their first explanation."""
    output, seen = [], set()
    for candidate in candidates:
        key = (candidate.get("source"), candidate.get("id") or candidate.get("property_id"))
        if key in seen:
            continue
        seen.add(key)
        output.append(candidate)
    return output
