"""Inspections (staff)."""
from fastapi import APIRouter, Depends

from core.db import db
from core.security import get_current_user

router = APIRouter()


@router.get("/inspections")
async def list_inspections(user: dict = Depends(get_current_user)):
    return await db.inspections.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)


@router.put("/inspections/{iid}")
async def update_inspection(iid: str, payload: dict, user: dict = Depends(get_current_user)):
    payload.pop("id", None); payload.pop("_id", None)
    await db.inspections.update_one({"id": iid}, {"$set": payload})
    return await db.inspections.find_one({"id": iid}, {"_id": 0})
