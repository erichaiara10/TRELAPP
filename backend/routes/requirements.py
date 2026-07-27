"""Requirements CRUD + public anonymous listing."""
from fastapi import APIRouter, Depends

from core.db import db, strip_id
from core.security import get_current_user
from models import Requirement, RequirementCreate

router = APIRouter()


@router.get("/requirements")
async def list_requirements(user: dict = Depends(get_current_user)):
    return await db.requirements.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)


@router.get("/requirements/public")
async def public_requirements():
    return await db.requirements.find(
        {"anonymous_public": True, "status": "active"},
        {"_id": 0, "customer_id": 0, "customer_name": 0}
    ).sort("created_at", -1).to_list(50)


@router.post("/requirements")
async def create_requirement(payload: RequirementCreate,
                             user: dict = Depends(get_current_user)):
    r = Requirement(**payload.model_dump()).model_dump()
    await db.requirements.insert_one(r)
    return strip_id(r)


@router.delete("/requirements/{rid}")
async def delete_requirement(rid: str, user: dict = Depends(get_current_user)):
    await db.requirements.delete_one({"id": rid})
    return {"ok": True}
