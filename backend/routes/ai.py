"""AI endpoints — Price Analysis + Nearby Amenities (Claude Sonnet 4.5 via Emergent LLM Key)."""
import json as _json
import logging
import os
import re

from fastapi import APIRouter, HTTPException

from core.comparable_evidence import ComparableEvidenceService
from core.db import db, new_id
from models import NearbyAmenitiesIn, PriceAnalysisIn

router = APIRouter()
logger = logging.getLogger("trel")
price_guidance = ComparableEvidenceService(db)


@router.post("/ai/price-analysis")
async def ai_price_analysis(payload: PriceAnalysisIn):
    """Combine indexed TREL-internal and external-market evidence.

    The calculation is deterministic and remains available without an AI key.
    No owner, advertiser, private address, source URL, or internal identifier is
    returned to the public client.
    """
    if payload.price <= 0:
        raise HTTPException(400, "Price must be greater than zero")
    if not payload.city and not payload.suburb:
        raise HTTPException(400, "City or suburb is required for a meaningful analysis")
    try:
        return await price_guidance.analyse(payload.model_dump())
    except Exception as exc:
        logger.exception("Price guidance failed")
        raise HTTPException(500, "Price comparison is temporarily unavailable") from exc


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
        raise HTTPException(503, "Nearby amenities are not configured")

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
