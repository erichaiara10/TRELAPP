"""AI endpoints — Price Analysis + Nearby Amenities (Claude Sonnet 4.5 via Emergent LLM Key)."""
import json as _json
import logging
import os
import re

from fastapi import APIRouter, HTTPException

from core.db import db, new_id
from models import NearbyAmenitiesIn, PriceAnalysisIn

router = APIRouter()
logger = logging.getLogger("trel")


@router.post("/ai/price-analysis")
async def ai_price_analysis(payload: PriceAnalysisIn):
    """Public endpoint — takes a user's property parameters, retrieves similar
    active listings from Mongo, asks Claude Sonnet 4.5 for a structured
    valuation, and returns a curated JSON response. Data sources (raw property
    IDs, agents, owners) are stripped before returning to the client."""
    if payload.price <= 0:
        raise HTTPException(400, "Price must be greater than zero")
    if not payload.city and not payload.suburb:
        raise HTTPException(400, "City or suburb is required for a meaningful analysis")

    query = {"status": "active", "listing_type": payload.listing_type,
             "property_type": payload.property_type}
    or_locs = []
    if payload.city:
        or_locs.append({"location": payload.city})
    if payload.suburb:
        or_locs.append({"suburb": payload.suburb})
    if or_locs:
        query["$or"] = or_locs
    similar = await db.properties.find(
        query,
        {"_id": 0, "title": 1, "property_type": 1, "suburb": 1, "location": 1,
         "price": 1, "bedrooms": 1, "street_name": 1, "nearby_landmark": 1}
    ).sort("created_at", -1).to_list(20)

    prices = [p["price"] for p in similar if isinstance(p.get("price"), (int, float))]
    local_avg = sum(prices) / len(prices) if prices else payload.price

    prompt = f"""You are a Papua New Guinea real estate valuation analyst. Given the seller's own listing
and a list of similar active listings in the same area, return a STRICT JSON object with these keys:
{{
  "range_min": <number, currency PGK>,
  "range_max": <number, currency PGK>,
  "average":   <number, currency PGK>,
  "verdict":   "fair" | "overpriced" | "underpriced",
  "recommendation": <short actionable sentence, max 25 words>,
  "comparables": [ {{ "title": <string>, "property_type": <string>, "suburb": <string>, "price": <number> }}, ... 3 to 5 items ]
}}

RULES:
- All prices are in PGK (Papua New Guinean Kina).
- Base your range on the comparable data supplied — do NOT invent listings.
- If there are fewer than 3 comparables, pick the closest ones to the seller's price.
- Never include agent names, owner names, listing IDs, or URLs.
- Verdict rules (against the average of comparables):
  * fair       = user_price is within ±10% of the average
  * overpriced = user_price is > 10% above average
  * underpriced= user_price is > 10% below average
- When multiple comparables exist, GIVE HIGHER WEIGHT to listings on the same street or near the same landmark as the seller (see fields `street_name` and `nearby_landmark`). Note this preference in your recommendation only if street/landmark data was helpful.
- Output ONLY the JSON object, no markdown, no prose.

SELLER LISTING:
  property_type    = {payload.property_type}
  listing_type     = {payload.listing_type}
  bedrooms         = {payload.bedrooms}
  city             = {payload.city}
  suburb           = {payload.suburb}
  street_name      = {payload.street_name or ""}
  nearby_landmark  = {payload.nearby_landmark or ""}
  price_PGK        = {payload.price}

SIMILAR ACTIVE LISTINGS (JSON):
{_json.dumps(similar, default=str)}
"""

    key = os.environ.get("EMERGENT_LLM_KEY")
    if not key:
        raise HTTPException(500, "AI service is not configured")

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = (LlmChat(
            api_key=key, session_id=new_id(),
            system_message="You are a real estate valuation analyst that returns strict JSON only.",
        ).with_model("anthropic", "claude-sonnet-4-5-20250929"))
        raw = await chat.send_message(UserMessage(text=prompt))
        text = (raw or "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```\s*$", "", text)
        data = _json.loads(text)
    except Exception as e:
        logger.warning("AI price analysis fell back to statistical baseline: %s", e)
        rng = 0.15
        data = {
            "range_min": round(local_avg * (1 - rng)),
            "range_max": round(local_avg * (1 + rng)),
            "average": round(local_avg),
            "verdict": ("overpriced" if payload.price > local_avg * 1.10
                        else "underpriced" if payload.price < local_avg * 0.90
                        else "fair"),
            "recommendation": "Statistical estimate — request an in-person valuation for a firm figure.",
            "comparables": [
                {"title": p.get("title") or "Comparable listing",
                 "property_type": p.get("property_type") or payload.property_type,
                 "suburb": p.get("suburb") or (payload.suburb or payload.city or ""),
                 "price": p.get("price") or 0}
                for p in similar[:5]
            ],
        }

    safe_comps = []
    for c in (data.get("comparables") or [])[:5]:
        safe_comps.append({
            "title": str(c.get("title", ""))[:120],
            "property_type": str(c.get("property_type", "")),
            "suburb": str(c.get("suburb", "")),
            "price": float(c.get("price") or 0),
        })
    return {
        "range_min": float(data.get("range_min") or 0),
        "range_max": float(data.get("range_max") or 0),
        "average":   float(data.get("average") or local_avg),
        "verdict":   data.get("verdict") if data.get("verdict") in {"fair", "overpriced", "underpriced"} else "fair",
        "recommendation": str(data.get("recommendation", ""))[:280],
        "comparables": safe_comps,
        "sample_size": len(similar),
    }


_ALLOWED_CATEGORIES = {"schools", "hospitals", "shopping", "beaches", "transport", "recreation"}


@router.post("/ai/nearby-amenities")
async def ai_nearby_amenities(payload: NearbyAmenitiesIn):
    """Public endpoint — returns a curated list of nearby amenities for a property
    location in Papua New Guinea. Uses Claude Sonnet 4.5 via Emergent LLM key."""
    if not (payload.city or payload.suburb):
        raise HTTPException(400, "City or suburb is required")

    location_label = ", ".join([x for x in [payload.suburb, payload.city, payload.province] if x])

    prompt = f"""You are a Papua New Guinea real estate concierge. A buyer is considering a property in
{location_label}. Return a STRICT JSON object listing nearby amenities across six categories, based
on your knowledge of that area.

SCHEMA:
{{
  "location_label": <string, echo of the input>,
  "categories": [
    {{
      "key": "schools" | "hospitals" | "shopping" | "beaches" | "transport" | "recreation",
      "label": <human-friendly title, e.g. "Schools & Education">,
      "items": [
        {{ "name": <string, real name if you know it>, "distance_hint": <e.g. "~5 min drive" or "within 2 km">, "note": <short helpful sentence, max 20 words> }},
        ...1 to 4 items per category
      ]
    }},
    ...
  ]
}}

RULES:
- Include AT MOST 4 items per category, and include only categories that have real, plausible amenities near this area.
- If you are unsure about a specific facility name, use a generic descriptor (e.g. "Local primary school") rather than inventing a name.
- Do NOT include phone numbers, addresses, or URLs.
- Keep each note under 20 words. Be factual and helpful.
- All distances should be approximate walking or driving hints, not exact figures.
- Output ONLY the JSON object, no markdown, no prose.

LOCATION:
  suburb   = {payload.suburb or ""}
  city     = {payload.city or ""}
  province = {payload.province or ""}
  property_type = {payload.property_type or ""}
"""

    key = os.environ.get("EMERGENT_LLM_KEY")
    if not key:
        raise HTTPException(500, "AI service is not configured")

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = (LlmChat(
            api_key=key, session_id=new_id(),
            system_message="You are a Papua New Guinea real estate concierge that returns strict JSON only.",
        ).with_model("anthropic", "claude-sonnet-4-5-20250929"))
        raw = await chat.send_message(UserMessage(text=prompt))
        text = (raw or "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```\s*$", "", text)
        data = _json.loads(text)
    except Exception as e:
        logger.warning("AI nearby amenities failed: %s", e)
        raise HTTPException(502, "Amenities service is temporarily unavailable")

    _url_re = re.compile(r"https?://\S+", re.IGNORECASE)
    _phone_re = re.compile(r"\+?\d[\d\s\-().]{6,}")

    def _clean(txt: str, cap: int) -> str:
        t = _url_re.sub("", txt or "")
        t = _phone_re.sub("", t)
        return re.sub(r"\s{2,}", " ", t).strip()[:cap]

    safe_categories = []
    for cat in (data.get("categories") or [])[:6]:
        ckey = str(cat.get("key", "")).lower().strip()
        if ckey not in _ALLOWED_CATEGORIES:
            continue
        items = []
        for it in (cat.get("items") or [])[:4]:
            items.append({
                "name": _clean(str(it.get("name", "")), 80),
                "distance_hint": _clean(str(it.get("distance_hint", "")), 40),
                "note": _clean(str(it.get("note", "")), 140),
            })
        if not items:
            continue
        safe_categories.append({
            "key": ckey,
            "label": str(cat.get("label", ckey.title()))[:60],
            "items": items,
        })

    return {
        "location_label": location_label,
        "categories": safe_categories,
        "disclaimer": "AI-generated summary. Verify details in person before making a decision.",
    }
