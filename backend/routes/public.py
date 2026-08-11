"""Public endpoints — captcha challenge, lead submit, inspection request,
public price-guidance runs."""
from fastapi import APIRouter, HTTPException

from core.db import db
from core.guidance import generate_guidance
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
    # Price-compare leads inherit their agent-team from the workflow the user was on
    if p["source"] == "price_compare":
        role = "leasing_agent" if p.get("payload", {}).get("workflow") in ("landlord", "renter") else "sales_agent"
    lead = Lead(source=p["source"], name=p["name"], email=p.get("email"),
                phone=p.get("phone"), message=p.get("message", ""),
                property_id=p.get("property_id"), property_title=prop_title,
                payload=p.get("payload", {}),
                assigned_agent_id=await auto_assign_agent(role)).model_dump()
    await db.leads.insert_one(lead)
    if payload.name:
        ctype = {"sell_form": "seller", "wanted_form": "buyer",
                 "corporate_form": "corporate", "management_form": "landlord",
                 "inspection_form": "buyer", "contact_form": "buyer",
                 "price_compare": "buyer"}.get(p["source"], "buyer")
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



# ---------- Public Price Compare ----------
@router.post("/public/guidance/run")
async def public_guidance_run(payload: dict):
    """Public guidance endpoint powering the 4 customer-facing Price Compare
    screens. Same GUIDE-1.0 engine as the admin; the workflow field selects
    the presentation slant (seller/buyer/landlord/renter)."""
    if payload.get("purpose") not in ("sale", "rent"):
        raise HTTPException(400, "purpose must be 'sale' or 'rent'")
    if not payload.get("suburb"):
        raise HTTPException(400, "Suburb is required for price guidance")
    workflow = payload.pop("workflow", "seller")
    if workflow not in ("seller", "buyer", "landlord", "renter"):
        raise HTTPException(400, "workflow must be seller|buyer|landlord|renter")
    try:
        out = await generate_guidance(payload, workflow=workflow, actor_id=None)
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    # Strip internal ids from the response — public users just need the shape
    r = out["result"]; comps = out["comparables"]
    subj_asking = payload.get("subject_asking_price")
    weighted_med = r.get("weighted_median")
    position = None
    if subj_asking and weighted_med:
        pct = (float(subj_asking) - float(weighted_med)) / float(weighted_med) * 100.0
        if pct < -10:
            position = "BELOW"
        elif pct > 10:
            position = "ABOVE"
        else:
            position = "WITHIN"
    return {
        "workflow": workflow,
        "purpose": payload["purpose"],
        "comparable_count": r["comparable_count"],
        "observed_range": r["observed_range"],
        "median": r["median"],
        "weighted_median": weighted_med,
        "trel_indicative_range": r["trel_indicative_range"],
        "confidence_label": r["confidence_label"],
        "confidence_score": r["confidence_score"],
        "position": position,
        "delta_pct": ((float(subj_asking) - float(weighted_med)) / float(weighted_med) * 100.0
                       if subj_asking and weighted_med else None),
        "algorithm_version": r["algorithm_version"],
        "config_version": r["config_version"],
        "comparables_sample": [
            {"tier": c["tier"], "quality_score": c["quality_score"],
             "recency_factor": c["recency_factor"], "value": c["value"],
             "inclusion_status": c["inclusion_status"]}
            for c in comps if c["inclusion_status"] == "included"
        ][:12],
    }
