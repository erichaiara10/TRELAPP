"""Locations — Province → City → Suburb (public + admin CRUD)."""
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from core.db import db, new_id, now_iso
from core.security import get_current_user
from models import CityIn, ProvinceIn, RenameIn, SuburbIn

router = APIRouter()


# ---- Public read ----
@router.get("/locations/provinces")
async def list_provinces():
    return await db.provinces.find({}, {"_id": 0}).sort("name", 1).to_list(500)


@router.get("/locations/cities")
async def list_cities(province_id: Optional[str] = None):
    q = {"province_id": province_id} if province_id else {}
    return await db.cities.find(q, {"_id": 0}).sort("name", 1).to_list(1000)


@router.get("/locations/suburbs")
async def list_suburbs(city_id: Optional[str] = None):
    q = {"city_id": city_id} if city_id else {}
    return await db.suburbs.find(q, {"_id": 0}).sort("name", 1).to_list(5000)


@router.post("/locations/suburbs")
async def create_public_suburb(payload: SuburbIn):
    """Public endpoint: any user submitting a form can add a new suburb for an existing city."""
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(400, "Suburb name is required")
    if len(name) > 80:
        raise HTTPException(400, "Suburb name too long")
    city = await db.cities.find_one({"id": payload.city_id})
    if not city:
        raise HTTPException(404, "City not found")
    existing = await db.suburbs.find_one({
        "name": {"$regex": f"^{re.escape(name)}$", "$options": "i"},
        "city_id": payload.city_id,
    })
    if existing:
        return {"id": existing["id"], "name": existing["name"], "city_id": existing["city_id"],
                "province_id": existing["province_id"],
                "source": existing.get("source", "admin"),
                "created_at": existing["created_at"]}
    doc = {"id": new_id(), "name": name, "city_id": payload.city_id,
           "province_id": city["province_id"], "source": "user", "created_at": now_iso()}
    await db.suburbs.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


# ---- Admin CRUD ----
@router.post("/admin/locations/provinces")
async def admin_create_province(payload: ProvinceIn, user: dict = Depends(get_current_user)):
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(400, "Province name is required")
    if await db.provinces.find_one({"name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}}):
        raise HTTPException(409, "Province already exists")
    doc = {"id": new_id(), "name": name, "created_at": now_iso()}
    await db.provinces.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


@router.put("/admin/locations/provinces/{province_id}")
async def admin_rename_province(province_id: str, payload: RenameIn,
                                user: dict = Depends(get_current_user)):
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(400, "Province name is required")
    r = await db.provinces.update_one({"id": province_id}, {"$set": {"name": name}})
    if r.matched_count == 0:
        raise HTTPException(404, "Province not found")
    return {"ok": True}


@router.delete("/admin/locations/provinces/{province_id}")
async def admin_delete_province(province_id: str, user: dict = Depends(get_current_user)):
    r = await db.provinces.delete_one({"id": province_id})
    if r.deleted_count == 0:
        raise HTTPException(404, "Province not found")
    city_ids = [c["id"] async for c in db.cities.find({"province_id": province_id},
                                                      {"_id": 0, "id": 1})]
    await db.cities.delete_many({"province_id": province_id})
    if city_ids:
        await db.suburbs.delete_many({"city_id": {"$in": city_ids}})
    return {"ok": True}


@router.post("/admin/locations/cities")
async def admin_create_city(payload: CityIn, user: dict = Depends(get_current_user)):
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(400, "City name is required")
    if not await db.provinces.find_one({"id": payload.province_id}):
        raise HTTPException(404, "Province not found")
    if await db.cities.find_one({
        "name": {"$regex": f"^{re.escape(name)}$", "$options": "i"},
        "province_id": payload.province_id,
    }):
        raise HTTPException(409, "City already exists in this province")
    doc = {"id": new_id(), "name": name, "province_id": payload.province_id,
           "created_at": now_iso()}
    await db.cities.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


@router.put("/admin/locations/cities/{city_id}")
async def admin_rename_city(city_id: str, payload: RenameIn,
                            user: dict = Depends(get_current_user)):
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(400, "City name is required")
    r = await db.cities.update_one({"id": city_id}, {"$set": {"name": name}})
    if r.matched_count == 0:
        raise HTTPException(404, "City not found")
    return {"ok": True}


@router.delete("/admin/locations/cities/{city_id}")
async def admin_delete_city(city_id: str, user: dict = Depends(get_current_user)):
    r = await db.cities.delete_one({"id": city_id})
    if r.deleted_count == 0:
        raise HTTPException(404, "City not found")
    await db.suburbs.delete_many({"city_id": city_id})
    return {"ok": True}


@router.post("/admin/locations/suburbs")
async def admin_create_suburb(payload: SuburbIn, user: dict = Depends(get_current_user)):
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(400, "Suburb name is required")
    city = await db.cities.find_one({"id": payload.city_id})
    if not city:
        raise HTTPException(404, "City not found")
    if await db.suburbs.find_one({
        "name": {"$regex": f"^{re.escape(name)}$", "$options": "i"},
        "city_id": payload.city_id,
    }):
        raise HTTPException(409, "Suburb already exists in this city")
    doc = {"id": new_id(), "name": name, "city_id": payload.city_id,
           "province_id": city["province_id"], "source": "admin", "created_at": now_iso()}
    await db.suburbs.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


@router.put("/admin/locations/suburbs/{suburb_id}")
async def admin_rename_suburb(suburb_id: str, payload: RenameIn,
                              user: dict = Depends(get_current_user)):
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(400, "Suburb name is required")
    r = await db.suburbs.update_one({"id": suburb_id}, {"$set": {"name": name}})
    if r.matched_count == 0:
        raise HTTPException(404, "Suburb not found")
    return {"ok": True}


@router.delete("/admin/locations/suburbs/{suburb_id}")
async def admin_delete_suburb(suburb_id: str, user: dict = Depends(get_current_user)):
    r = await db.suburbs.delete_one({"id": suburb_id})
    if r.deleted_count == 0:
        raise HTTPException(404, "Suburb not found")
    return {"ok": True}
