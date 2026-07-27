"""Dynamic property-types CRUD (admin-managed via inline dropdown)."""
from fastapi import APIRouter, Depends, HTTPException

from core.db import db, strip_id
from core.security import get_current_user
from models import PropertyType, PropertyTypeCreate

router = APIRouter()


@router.get("/property-types")
async def list_property_types_public():
    """Public: only active types, ordered."""
    return await db.property_types.find({"is_active": True}, {"_id": 0}) \
        .sort([("order", 1), ("name", 1)]).to_list(200)


@router.get("/property-types/all")
async def list_property_types_all(user: dict = Depends(get_current_user)):
    return await db.property_types.find({}, {"_id": 0}) \
        .sort([("order", 1), ("name", 1)]).to_list(500)


@router.post("/property-types")
async def create_property_type(payload: PropertyTypeCreate,
                               user: dict = Depends(get_current_user)):
    if not payload.name.strip():
        raise HTTPException(400, "Name is required")
    clean_name = payload.name.strip()
    exists = await db.property_types.find_one({"name": clean_name}, {"_id": 0})
    if exists:
        raise HTTPException(409, "A property type with this name already exists")
    data = payload.model_dump()
    data["name"] = clean_name
    doc = PropertyType(**data).model_dump()
    await db.property_types.insert_one(doc)
    return strip_id(doc)


@router.delete("/property-types/{tid}")
async def delete_property_type(tid: str, user: dict = Depends(get_current_user)):
    await db.property_types.delete_one({"id": tid})
    return {"ok": True}
