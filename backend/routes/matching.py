"""Rule-based requirement → property matching engine."""
from fastapi import APIRouter, Depends, HTTPException

from core.db import db
from core.security import get_current_user

router = APIRouter()


def _score_intent(req: dict, prop: dict) -> int:
    intent, ltype = req.get("intent"), prop.get("listing_type")
    if intent == "buy" and ltype == "sale":
        return 20
    if intent == "rent" and ltype == "rent":
        return 20
    if intent == "either":
        return 10
    return 0


def _score_type(req: dict, prop: dict) -> int:
    if req.get("property_type") and req["property_type"] == prop.get("property_type"):
        return 20
    return 0


def _score_price(req: dict, prop: dict) -> int:
    price = prop.get("price", 0)
    lo, hi = req.get("min_price") or 0, req.get("max_price") or 0
    s = 0
    if hi and price <= hi:
        s += 15
    if not hi:
        s += 5
    if lo and price >= lo:
        s += 5
    return s


def _score_bedrooms(req: dict, prop: dict) -> int:
    if (prop.get("bedrooms") or 0) >= (req.get("min_bedrooms") or 0):
        return 15
    return 0


def _score_location(req: dict, prop: dict) -> int:
    locs = req.get("locations") or []
    if not locs or prop.get("location") in locs or prop.get("suburb") in locs:
        return 15
    return 0


def score_match(req: dict, prop: dict) -> int:
    if prop.get("status") != "active":
        return 0
    total = _score_intent(req, prop) + _score_type(req, prop) + _score_price(req, prop) \
        + _score_bedrooms(req, prop) + _score_location(req, prop)
    return max(0, total)


@router.get("/matching/{requirement_id}")
async def match_requirement(requirement_id: str, user: dict = Depends(get_current_user)):
    req = await db.requirements.find_one({"id": requirement_id}, {"_id": 0})
    if not req:
        raise HTTPException(404, "Requirement not found")
    props = await db.properties.find({"status": "active"}, {"_id": 0}).to_list(500)
    scored = [{"property": p, "score": score_match(req, p)} for p in props]
    scored.sort(key=lambda x: x["score"], reverse=True)
    return {"requirement": req, "matches": scored[:20]}
