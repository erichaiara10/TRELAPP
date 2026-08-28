"""Properties CRUD backed by the controlled integrated Property gateway."""
import math
import re
from fastapi import APIRouter, Depends, HTTPException

from core.account_policy import STAFF, account_category, require_property_writer
from core.db import db, now_iso
from core.integrated_property_service import DuplicatePropertyError, PartialWriteError
from core.property_advertising_rules import public_listing_visible
from core.property_repository import PropertyRepository
from core.security import get_current_user, get_optional_user
from models import Property, PropertyCreate, PropertyFilters

router = APIRouter()
repository = PropertyRepository(db)

LISTING_STATUSES = {"draft", "active", "under_offer", "sold", "leased", "withdrawn"}
OWNER_RELATIONSHIPS = {"OWNER", "JOINT_OWNER", "AUTHORISED_AGENT", "AUTHORISED_REPRESENTATIVE"}
AUTHORITY_STATUSES = {"PENDING", "VERIFIED", "REJECTED", "EXPIRED"}
TENURE_TYPES = {None, "", "STATE_LEASE", "FREEHOLD", "CUSTOMARY", "OTHER"}


def _q_match(field, value):
    return {field: value} if value else {}


def _q_gte(field, value):
    return {field: {"$gte": value}} if value is not None else {}


def _q_price(min_price, max_price):
    if min_price is None and max_price is None:
        return {}
    price = {}
    if min_price is not None:
        price["$gte"] = min_price
    if max_price is not None:
        price["$lte"] = max_price
    return {"price": price}


def _q_search(value):
    if not value:
        return {}
    return {"$or": [
        {field: {"$regex": value, "$options": "i"}}
        for field in ("title", "description", "suburb", "location")
    ]}


def _q_bool(field, value):
    return {field: value} if value is not None else {}


def build_property_query(filters: dict) -> dict:
    query = {}
    for part in (
        _q_match("listing_type", filters.get("listing_type")),
        _q_match("property_type", filters.get("property_type")),
        _q_match("location", filters.get("location")),
        _q_match("status", filters.get("status")),
        _q_gte("bedrooms", filters.get("bedrooms")),
        _q_bool("featured", filters.get("featured")),
        _q_price(filters.get("min_price"), filters.get("max_price")),
        _q_search(filters.get("q")),
    ):
        query.update(part)
    return query


def _public_property(document: dict) -> dict:
    safe = dict(document)
    for key in (
        "owner_name", "owner_email", "owner_phone", "owner_customer_id",
        "documents", "authority_status", "title_reference", "assigned_agent_id",
        "created_by", "street_id", "district_id", "local_area_id",
    ):
        safe.pop(key, None)
    return safe


async def enforce_scheme(payload: dict, enforce_publication: bool = True) -> dict:
    for key, label in [
        ("title", "Title"),
        ("listing_type", "Listing Type"),
        ("property_type", "Property Type"),
        ("province", "Province"),
    ]:
        if not str(payload.get(key) or "").strip():
            raise HTTPException(400, f"{label} is required")
    if payload["listing_type"] not in ("sale", "rent"):
        raise HTTPException(400, "Listing Type must be 'sale' or 'rent'")
    if payload.get("currency", "PGK") != "PGK":
        raise HTTPException(400, "Currency must be PGK")
    if payload.get("status") not in LISTING_STATUSES:
        raise HTTPException(400, "Invalid Property/Listing Status")
    if payload.get("owner_relationship", "OWNER") not in OWNER_RELATIONSHIPS:
        raise HTTPException(400, "Invalid relationship to Property")
    if payload.get("authority_status", "PENDING") not in AUTHORITY_STATUSES:
        raise HTTPException(400, "Invalid Authority Verification Status")
    if payload.get("tenure_type") not in TENURE_TYPES:
        raise HTTPException(400, "Invalid Tenure Type")
    if payload["listing_type"] == "sale" and payload.get("status") == "leased":
        raise HTTPException(400, "A sale listing cannot have Leased status")
    if payload["listing_type"] == "rent" and payload.get("status") == "sold":
        raise HTTPException(400, "A rental listing cannot have Sold status")
    if float(payload.get("price") or 0) <= 0:
        raise HTTPException(400, "Price must be greater than zero")
    for key, label in (
        ("allotment_number", "Lot Number"),
        ("section_number", "Section Number"),
        ("full_portion_number", "Portion Number"),
    ):
        value = payload.get(key)
        if value not in {None, ""} and not re.fullmatch(r"\d+", str(value).strip()):
            raise HTTPException(400, f"{label} must contain digits only")
    for key, label in (
        ("total_area_ha", "Total Area"),
        ("building_area_ha", "Building / Floor Area"),
    ):
        value = payload.get(key)
        if value in {None, ""}:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise HTTPException(400, f"{label} must be a number in hectares (ha)")
        if not math.isfinite(number) or number <= 0:
            raise HTTPException(400, f"{label} must be greater than zero hectares (ha)")

    type_query = {"id": payload["property_type_id"]} if payload.get("property_type_id") else {
        "name": payload["property_type"].strip()
    }
    type_query["is_active"] = True
    property_type = await db.property_types.find_one(
        type_query, {"_id": 0, "id": 1, "name": 1, "legal_scheme": 1}
    )
    if not property_type:
        raise HTTPException(400, "Select an active Property Type")
    payload["property_type_id"] = property_type["id"]
    payload["property_type"] = property_type["name"]

    scheme = property_type.get("legal_scheme")
    if scheme == "portion":
        if not str(payload.get("full_portion_number") or "").strip():
            raise HTTPException(400, "Portion Number is required for this property type")
        payload["allotment_number"] = None
        payload["section_number"] = None
        payload["street_name"] = None
        if not str(payload.get("location") or payload.get("district") or "").strip():
            raise HTTPException(400, "Location or town is required for portion/customary property")
    elif scheme == "lot_section_street":
        for key, label in [
            ("allotment_number", "Lot Number"),
            ("section_number", "Section Number"),
        ]:
            if not str(payload.get(key) or "").strip():
                raise HTTPException(400, f"{label} is required for this property type")
        if not any(str(payload.get(key) or "").strip() for key in ("location", "suburb", "street_name")):
            raise HTTPException(400, "Town, Suburb or Street is required for this property type")
        payload["full_portion_number"] = None

    if payload.get("listing_type") == "sale" and float(payload.get("total_area_ha") or 0) <= 0:
        raise HTTPException(400, "Total Area (hectares) is required for sale listings")
    if repository.storage_mode == "integrated" and not str(payload.get("owner_name") or "").strip():
        raise HTTPException(400, "Owner name is required")
    if enforce_publication and payload.get("status") in {"active", "under_offer"} and payload.get("authority_status") != "VERIFIED":
        raise HTTPException(400, "Authority must be verified before a listing can be active")
    document_types = {item.get("document_type") for item in payload.get("documents") or []}
    if payload.get("owner_relationship") in {"AUTHORISED_AGENT", "AUTHORISED_REPRESENTATIVE"} \
            and "AUTHORITY_LETTER" not in document_types:
        raise HTTPException(400, "An Authority Letter is required for an authorised agent or representative")
    return payload


def _raise_duplicate(exc: DuplicatePropertyError):
    raise HTTPException(
        status_code=409,
        detail={
            "code": "POSSIBLE_DUPLICATE_PROPERTY",
            "message": "A possible matching property already exists",
            "candidates": exc.candidates,
        },
    )


@router.get("/properties")
async def list_properties(
    filters: PropertyFilters = Depends(),
    user=Depends(get_optional_user),
):
    query = build_property_query(filters.model_dump(exclude={"limit", "mine"}))
    # Scope the response when the caller asks for `mine=true`. Staff see
    # every property; non-staff (Property Advertisers etc.) only see the
    # listings they themselves created. Anonymous callers get 401 — the
    # advertiser workspace requires a session.
    if filters.mine:
        if not user:
            raise HTTPException(401, "Authentication required for mine=true")
        if account_category(user) != STAFF:
            query["created_by"] = user["id"]
    elif not user or account_category(user) != STAFF:
        query["status"] = "active"
    rows = await repository.list(query, filters.limit)
    if filters.mine or (user and account_category(user) == STAFF):
        return rows
    return [_public_property(row) for row in rows if public_listing_visible("PUBLISHED", row.get("status"))]


@router.post("/properties/duplicate-check")
async def check_property_duplicates(
    payload: PropertyCreate,
    user: dict = Depends(require_property_writer),
):
    data = await enforce_scheme(payload.model_dump(), enforce_publication=False)
    candidates = await repository.duplicate_check(data)
    return {"has_possible_duplicates": bool(candidates), "candidates": candidates}


@router.get("/properties/{pid}")
async def get_property(pid: str, public_view: bool = False, user=Depends(get_optional_user)):
    document = await repository.get(pid)
    if not document:
        raise HTTPException(404, "Property not found")
    privileged = bool(user and (account_category(user) == STAFF or document.get("created_by") == user.get("id")))
    if privileged and not public_view:
        return document
    if not public_listing_visible("PUBLISHED", document.get("status")):
        availability = str(document.get("status") or "unavailable").upper()
        if document.get("listing_reference"):
            lifecycle = await db.advertiser_listing_lifecycle.find_one(
                {"listing_id": document["listing_reference"]}, {"_id": 0, "status": 1}
            )
            availability = str((lifecycle or {}).get("status") or availability).upper()
        raise HTTPException(410, {
            "code": "PROPERTY_UNAVAILABLE",
            "availability": availability,
            "message": "This property is no longer available",
        })
    return _public_property(document)


@router.post("/properties")
async def create_property(
    payload: PropertyCreate,
    user: dict = Depends(require_property_writer),
):
    data = await enforce_scheme(payload.model_dump())
    document = Property(**data).model_dump()
    try:
        return await repository.create(document, user)
    except DuplicatePropertyError as exc:
        _raise_duplicate(exc)
    except PartialWriteError as exc:
        raise HTTPException(500, {
            "code": "PARTIAL_WRITE_FAILURE",
            "message": "Property save failed partway. The change was rolled back — please retry.",
            "failure_id": exc.failure_id,
        })
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.put("/properties/{pid}")
async def update_property(
    pid: str,
    payload: dict,
    user: dict = Depends(require_property_writer),
):
    payload["updated_at"] = now_iso()
    payload.pop("id", None)
    payload.pop("_id", None)
    payload.pop("land_category", None)
    existing = await repository.get(pid) or {}
    if not existing:
        raise HTTPException(404, "Property not found")
    merged = await enforce_scheme({**existing, **payload})
    try:
        result = await repository.update(pid, merged, user)
    except DuplicatePropertyError as exc:
        _raise_duplicate(exc)
    except PartialWriteError as exc:
        raise HTTPException(500, {
            "code": "PARTIAL_WRITE_FAILURE",
            "message": "Property update failed partway. The change was rolled back — please retry.",
            "failure_id": exc.failure_id,
        })
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if not result:
        raise HTTPException(404, "Property not found")
    return result


@router.delete("/properties/{pid}")
async def delete_property(
    pid: str,
    user: dict = Depends(require_property_writer),
):
    if not await repository.delete(pid, user):
        raise HTTPException(404, "Property not found")
    return {"ok": True, "archived": True}


@router.post("/properties/{pid}/restore")
async def restore_property(
    pid: str,
    user: dict = Depends(require_property_writer),
):
    if not await repository.restore(pid, user):
        raise HTTPException(404, "Archived property not found")
    return {"ok": True, "restored": True}
