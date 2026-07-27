"""Leads CRUD + Communications history (leads + customers)."""
from fastapi import APIRouter, Depends, HTTPException

from core.db import db, now_iso, strip_id
from core.security import get_current_user
from models import Communication, CommunicationCreate

router = APIRouter()


@router.get("/leads")
async def list_leads(user: dict = Depends(get_current_user)):
    return await db.leads.find({}, {"_id": 0}).sort("created_at", -1).to_list(2000)


@router.put("/leads/{lid}")
async def update_lead(lid: str, payload: dict, user: dict = Depends(get_current_user)):
    payload.pop("id", None); payload.pop("_id", None)
    existing = await db.leads.find_one({"id": lid}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Lead not found")
    if existing.get("converted_at"):
        raise HTTPException(409, f"Lead is locked — already converted to property {existing.get('converted_property_id')}")
    if payload.get("status") == "converted" and payload.get("property_id") and not existing.get("converted_at"):
        payload["converted_at"] = now_iso()
        payload["converted_property_id"] = payload["property_id"]
    await db.leads.update_one({"id": lid}, {"$set": payload})
    return await db.leads.find_one({"id": lid}, {"_id": 0})


@router.delete("/leads/{lid}")
async def delete_lead(lid: str, user: dict = Depends(get_current_user)):
    existing = await db.leads.find_one({"id": lid}, {"_id": 0, "converted_at": 1, "converted_property_id": 1})
    if existing and existing.get("converted_at"):
        raise HTTPException(409, f"Lead is locked — already converted to property {existing.get('converted_property_id')}")
    await db.leads.delete_one({"id": lid})
    # Cascade delete communications (both new schema + legacy lead_id-only)
    await db.communications.delete_many({
        "$or": [{"parent_type": "lead", "parent_id": lid}, {"lead_id": lid}]
    })
    return {"ok": True}


# ---- Communications ----
def _match_parent(parent_type: str, parent_id: str) -> dict:
    """Match either the new (parent_type + parent_id) schema OR the legacy lead_id field."""
    if parent_type == "lead":
        return {"$or": [
            {"parent_type": "lead", "parent_id": parent_id},
            {"lead_id": parent_id, "parent_type": {"$exists": False}},
        ]}
    return {"parent_type": parent_type, "parent_id": parent_id}


async def _create_comm(parent_type: str, parent_id: str, payload: CommunicationCreate,
                       user: dict) -> dict:
    body = payload.body.strip()
    if not body:
        raise HTTPException(400, "Body is required")
    kwargs = {
        "parent_type": parent_type, "parent_id": parent_id,
        "kind": payload.kind, "direction": payload.direction,
        "subject": payload.subject, "body": body,
        "agent_id": user["id"], "agent_name": user["name"],
    }
    if parent_type == "lead":
        kwargs["lead_id"] = parent_id
    else:
        kwargs["customer_id"] = parent_id
    c = Communication(**kwargs).model_dump()
    await db.communications.insert_one(c)
    return strip_id(c)


@router.get("/leads/{lid}/communications")
async def list_lead_communications(lid: str, user: dict = Depends(get_current_user)):
    return await db.communications.find(_match_parent("lead", lid), {"_id": 0}) \
        .sort("created_at", 1).to_list(500)


@router.post("/leads/{lid}/communications")
async def create_lead_communication(lid: str, payload: CommunicationCreate,
                                    user: dict = Depends(get_current_user)):
    lead = await db.leads.find_one({"id": lid}, {"_id": 0, "id": 1})
    if not lead:
        raise HTTPException(404, "Lead not found")
    return await _create_comm("lead", lid, payload, user)


@router.get("/customers/{cid}/communications")
async def list_customer_communications(cid: str, user: dict = Depends(get_current_user)):
    return await db.communications.find(_match_parent("customer", cid), {"_id": 0}) \
        .sort("created_at", 1).to_list(500)


@router.post("/customers/{cid}/communications")
async def create_customer_communication(cid: str, payload: CommunicationCreate,
                                        user: dict = Depends(get_current_user)):
    customer = await db.customers.find_one({"id": cid}, {"_id": 0, "id": 1})
    if not customer:
        raise HTTPException(404, "Customer not found")
    return await _create_comm("customer", cid, payload, user)


@router.delete("/communications/{cid}")
async def delete_communication(cid: str, user: dict = Depends(get_current_user)):
    await db.communications.delete_one({"id": cid})
    return {"ok": True}
