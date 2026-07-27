"""Tasks CRUD."""
from fastapi import APIRouter, Depends

from core.db import db, strip_id
from core.security import get_current_user
from models import Task, TaskCreate

router = APIRouter()


@router.get("/tasks")
async def list_tasks(user: dict = Depends(get_current_user)):
    return await db.tasks.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)


@router.post("/tasks")
async def create_task(payload: TaskCreate, user: dict = Depends(get_current_user)):
    t = Task(**payload.model_dump()).model_dump()
    await db.tasks.insert_one(t)
    return strip_id(t)


@router.put("/tasks/{tid}")
async def update_task(tid: str, payload: dict, user: dict = Depends(get_current_user)):
    payload.pop("id", None); payload.pop("_id", None)
    await db.tasks.update_one({"id": tid}, {"$set": payload})
    return await db.tasks.find_one({"id": tid}, {"_id": 0})


@router.delete("/tasks/{tid}")
async def delete_task(tid: str, user: dict = Depends(get_current_user)):
    await db.tasks.delete_one({"id": tid})
    return {"ok": True}
