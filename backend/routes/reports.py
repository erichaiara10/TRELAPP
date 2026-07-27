"""Simple aggregate reports."""
from fastapi import APIRouter, Depends

from core.db import db
from core.security import get_current_user

router = APIRouter()


@router.get("/reports/summary")
async def reports_summary(user: dict = Depends(get_current_user)):
    async def count(coll, q=None):
        return await coll.count_documents(q or {})
    return {
        "properties_active": await count(db.properties, {"status": "active"}),
        "properties_sold": await count(db.properties, {"status": "sold"}),
        "properties_leased": await count(db.properties, {"status": "leased"}),
        "leads_new": await count(db.leads, {"status": "new"}),
        "leads_total": await count(db.leads),
        "customers": await count(db.customers),
        "requirements_active": await count(db.requirements, {"status": "active"}),
        "inspections_open": await count(db.inspections, {"status": {"$in": ["requested", "scheduled"]}}),
        "tasks_open": await count(db.tasks, {"status": {"$in": ["open", "in_progress"]}}),
    }


@router.get("/reports/leads_by_source")
async def leads_by_source(user: dict = Depends(get_current_user)):
    rows = await db.leads.aggregate([{"$group": {"_id": "$source", "count": {"$sum": 1}}}]) \
        .to_list(100)
    return [{"source": r["_id"], "count": r["count"]} for r in rows]
