"""Customers CRUD."""
from fastapi import APIRouter, Depends

from core.db import db, strip_id
from core.security import get_current_user
from models import Customer, CustomerCreate

router = APIRouter()


@router.get("/customers")
async def list_customers(user: dict = Depends(get_current_user)):
    return await db.customers.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)


@router.post("/customers")
async def create_customer(payload: CustomerCreate, user: dict = Depends(get_current_user)):
    c = Customer(**payload.model_dump()).model_dump()
    await db.customers.insert_one(c)
    return strip_id(c)


@router.put("/customers/{cid}")
async def update_customer(cid: str, payload: dict, user: dict = Depends(get_current_user)):
    payload.pop("id", None); payload.pop("_id", None)
    await db.customers.update_one({"id": cid}, {"$set": payload})
    return await db.customers.find_one({"id": cid}, {"_id": 0})


@router.delete("/customers/{cid}")
async def delete_customer(cid: str, user: dict = Depends(get_current_user)):
    await db.customers.delete_one({"id": cid})
    # Cascade delete customer communications
    await db.communications.delete_many({"parent_type": "customer", "parent_id": cid})
    return {"ok": True}
