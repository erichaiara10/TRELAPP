"""Public endpoints — captcha challenge, lead submit, inspection request."""
from fastapi import APIRouter, HTTPException

from core.db import db
from core.notify import auto_assign_agent, notify
from core.security import captcha_encode, captcha_pair, captcha_verify, honeypot_check
from models import (
    Customer, Inspection, InspectionCreate, Lead, LeadCreate, Requirement,
)

router = APIRouter()


@router.get("/public/challenge")
async def get_public_challenge():
    q, a = captcha_pair()
    return {"question": q, "token": captcha_encode(a)}


@router.post("/public/leads")
async def public_create_lead(payload: LeadCreate):
    honeypot_check(payload.hp_website)
    captcha_verify(payload.verification_token, payload.verification_answer)
    p = payload.model_dump()
    prop_title = None
    if p.get("property_id"):
        prop = await db.properties.find_one({"id": p["property_id"]}, {"_id": 0, "title": 1})
        if prop:
            prop_title = prop["title"]
    role = "leasing_agent" if p["source"] == "management_form" else "sales_agent"
    lead = Lead(source=p["source"], name=p["name"], email=p.get("email"),
                phone=p.get("phone"), message=p.get("message", ""),
                property_id=p.get("property_id"), property_title=prop_title,
                payload=p.get("payload", {}),
                assigned_agent_id=await auto_assign_agent(role)).model_dump()
    await db.leads.insert_one(lead)
    if payload.name:
        ctype = {"sell_form": "seller", "wanted_form": "buyer",
                 "corporate_form": "corporate", "management_form": "landlord",
                 "inspection_form": "buyer", "contact_form": "buyer"}.get(p["source"], "buyer")
        cust = Customer(name=payload.name, email=payload.email, phone=payload.phone,
                        customer_type=ctype, source=p["source"],
                        assigned_agent_id=lead["assigned_agent_id"]).model_dump()
        await db.customers.insert_one(cust)
        await db.leads.update_one({"id": lead["id"]}, {"$set": {"customer_id": cust["id"]}})
    if p["source"] in ("wanted_form", "corporate_form"):
        pd = p.get("payload", {})
        req = Requirement(customer_name=payload.name, intent=pd.get("intent", "buy"),
                          property_type=pd.get("property_type"),
                          min_price=pd.get("min_price", 0),
                          max_price=pd.get("max_price", 0),
                          min_bedrooms=pd.get("min_bedrooms", 0),
                          locations=pd.get("locations", []),
                          notes=payload.message or "",
                          is_corporate=(p["source"] == "corporate_form")).model_dump()
        await db.requirements.insert_one(req)
        await db.leads.update_one({"id": lead["id"]}, {"$set": {"requirement_id": req["id"]}})
    await notify(f"New {p['source']} enquiry from {payload.name}",
                 payload.message or "See lead in dashboard", payload.email)
    return {"ok": True, "lead_id": lead["id"]}


@router.post("/public/inspections")
async def public_create_inspection(payload: InspectionCreate):
    honeypot_check(payload.hp_website)
    captcha_verify(payload.verification_token, payload.verification_answer)
    prop = await db.properties.find_one({"id": payload.property_id}, {"_id": 0, "title": 1})
    if not prop:
        raise HTTPException(404, "Property not found")
    ins = Inspection(property_id=payload.property_id, property_title=prop["title"],
                     customer_name=payload.customer_name,
                     customer_phone=payload.customer_phone,
                     customer_email=payload.customer_email,
                     preferred_date=payload.preferred_date,
                     assigned_agent_id=await auto_assign_agent("sales_agent")).model_dump()
    await db.inspections.insert_one(ins)
    lead = Lead(source="inspection_form", name=payload.customer_name,
                email=payload.customer_email, phone=payload.customer_phone,
                property_id=payload.property_id, property_title=prop["title"],
                payload={"preferred_date": payload.preferred_date},
                assigned_agent_id=ins["assigned_agent_id"]).model_dump()
    await db.leads.insert_one(lead)
    await notify(f"New inspection request: {prop['title']}",
                 payload.customer_name, payload.customer_email)
    return {"ok": True, "inspection_id": ins["id"]}
