"""Customers CRUD."""
from fastapi import APIRouter, Depends, HTTPException

from core.db import db, strip_id
from core.security import get_current_user
from models import Customer, CustomerCreate

router = APIRouter()


ALLOWED_CUSTOMER_TYPES = {"buyer", "seller", "tenant", "landlord", "corporate"}


def _validate_customer(payload: CustomerCreate):
    """Strict server-side validation for admin-created customers."""
    if not payload.name.strip():
        raise HTTPException(400, "Name is required")
    if not (payload.email or "").strip():
        raise HTTPException(400, "Email is required")
    if not (payload.phone or "").strip():
        raise HTTPException(400, "Phone is required")
    ctype = (payload.customer_type or "").strip()
    if not ctype:
        raise HTTPException(400, "Customer type is required")
    if ctype not in ALLOWED_CUSTOMER_TYPES:
        raise HTTPException(400,
            f"Customer type must be one of: {', '.join(sorted(ALLOWED_CUSTOMER_TYPES))}")


@router.get("/customers")
async def list_customers(user: dict = Depends(get_current_user)):
    return await db.customers.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)


@router.post("/customers")
async def create_customer(payload: CustomerCreate, user: dict = Depends(get_current_user)):
    _validate_customer(payload)
    c = Customer(**payload.model_dump()).model_dump()
    await db.customers.insert_one(c)
    return strip_id(c)


@router.put("/customers/{cid}")
async def update_customer(cid: str, payload: dict, user: dict = Depends(get_current_user)):
    payload.pop("id", None); payload.pop("_id", None)
    # Apply the same strict rules on edit (using merged view so partial updates work)
    existing = await db.customers.find_one({"id": cid}, {"_id": 0}) or {}
    merged = {**existing, **payload}
    _validate_customer(CustomerCreate(**{k: merged.get(k) for k in
        ("name", "email", "phone", "customer_type", "company",
         "notes", "source", "assigned_agent_id")}))
    await db.customers.update_one({"id": cid}, {"$set": payload})
    return await db.customers.find_one({"id": cid}, {"_id": 0})


@router.delete("/customers/{cid}")
async def delete_customer(cid: str, user: dict = Depends(get_current_user)):
    await db.customers.delete_one({"id": cid})
    # Cascade delete customer communications
    await db.communications.delete_many({"parent_type": "customer", "parent_id": cid})
    return {"ok": True}
