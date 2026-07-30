"""Properties CRUD + dynamic legal-scheme enforcement."""
from fastapi import APIRouter, Depends, HTTPException

from core.db import db, now_iso, strip_id
from core.security import get_current_user
from models import Property, PropertyCreate, PropertyFilters

router = APIRouter()


# ---- Query builders ----
def _q_match(field, value):
    return {field: value} if value else {}


def _q_gte(field, value):
    return {field: {"$gte": value}} if value is not None else {}


def _q_price(min_price, max_price):
    if min_price is None and max_price is None:
        return {}
    pr = {}
    if min_price is not None:
        pr["$gte"] = min_price
    if max_price is not None:
        pr["$lte"] = max_price
    return {"price": pr}


def _q_search(q):
    if not q:
        return {}
    return {"$or": [{f: {"$regex": q, "$options": "i"}}
                    for f in ("title", "description", "suburb", "location")]}


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


async def enforce_scheme(payload: dict) -> dict:
    """Validate a property payload against the global field rules AND the
    dynamic legal-scheme rules. Also wipes fields that don't apply so the DB
    stays consistent."""
    # ---- Always-required fields ----
    for k, label in [
        ("title", "Title"),
        ("listing_type", "Listing Type"),
        ("property_type", "Property Type"),
        ("province", "Province"),
        ("location", "City"),
        ("suburb", "Suburb"),
    ]:
        if not str(payload.get(k) or "").strip():
            raise HTTPException(400, f"{label} is required")
    if payload["listing_type"] not in ("sale", "rent"):
        raise HTTPException(400, "Listing Type must be 'sale' or 'rent'")
    if not (float(payload.get("price") or 0) > 0):
        raise HTTPException(400, "Price must be greater than zero")

    # ---- Legal scheme rules ----
    ptype = payload["property_type"].strip()
    t = await db.property_types.find_one({"name": ptype, "is_active": True},
                                         {"_id": 0, "legal_scheme": 1})
    scheme = (t or {}).get("legal_scheme")
    if scheme == "portion":
        if not str(payload.get("full_portion_number") or "").strip():
            raise HTTPException(400, "Portion Number is required for this property type")
        payload["allotment_number"] = None
        payload["section_number"] = None
        payload["street_name"] = None
    elif scheme == "lot_section_street":
        for k, label in [("allotment_number", "Lot Number"),
                         ("section_number", "Section Number"),
                         ("street_name", "Street Name")]:
            if not str(payload.get(k) or "").strip():
                raise HTTPException(400, f"{label} is required for this property type")
        payload["full_portion_number"] = None
    if payload.get("listing_type") == "sale" and not (payload.get("total_area_ha") or 0) > 0:
        raise HTTPException(400, "Total Area (hectares) is required for sale listings")
    return payload


@router.get("/properties")
async def list_properties(filters: PropertyFilters = Depends()):
    query = build_property_query(filters.model_dump(exclude={"limit"}))
    return await db.properties.find(query, {"_id": 0}).sort("created_at", -1).to_list(filters.limit)


@router.get("/properties/{pid}")
async def get_property(pid: str):
    doc = await db.properties.find_one({"id": pid}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Property not found")
    return doc


@router.post("/properties")
async def create_property(payload: PropertyCreate, user: dict = Depends(get_current_user)):
    data = await enforce_scheme(payload.model_dump())
    p = Property(**data).model_dump()
    await db.properties.insert_one(p)
    return strip_id(p)


@router.put("/properties/{pid}")
async def update_property(pid: str, payload: dict, user: dict = Depends(get_current_user)):
    payload["updated_at"] = now_iso()
    payload.pop("id", None); payload.pop("_id", None)
    payload.pop("land_category", None)  # legacy field — no longer stored
    existing = await db.properties.find_one({"id": pid}, {"_id": 0}) or {}
    merged = {**existing, **payload}
    await enforce_scheme(merged)
    # persist the cleaned merged view so wiped fields are actually cleared
    payload["allotment_number"] = merged.get("allotment_number")
    payload["section_number"] = merged.get("section_number")
    payload["street_name"] = merged.get("street_name")
    payload["full_portion_number"] = merged.get("full_portion_number")
    await db.properties.update_one({"id": pid}, {"$set": payload})
    return await db.properties.find_one({"id": pid}, {"_id": 0})


@router.delete("/properties/{pid}")
async def delete_property(pid: str, user: dict = Depends(get_current_user)):
    await db.properties.delete_one({"id": pid})
    return {"ok": True}
