"""Market Price Guidance engine — GUIDE-1.0.

Public entry: `generate_guidance(subject, workflow, actor_id=None)`

Pool observations from BOTH sources so Phase 1 can produce results before
scrapers are wired:
  * `market_listings` — external evidence (uses their price + last_seen)
  * `properties` linked via `master_property_id` — internal TREL evidence
    (uses their price + updated_at, filtered by matching listing_type→purpose)

Algorithm follows the spec:
  1. Classify subject
  2. Build direct pool across 3 location tiers
  3. Hard filters (purpose, class, unit scope)
  4. Deduplicate by master_id (keep latest per purpose)
  5. Score CQS 0-100
  6. Apply recency weighting
  7. IQR outlier removal (only if >= 6 comps)
  8. Weighted median + P25/P75 range
  9. Confidence label
 10. Persist valuation_request + guidance_result + guidance_comparables rows
"""
from __future__ import annotations

import statistics
from datetime import datetime, timezone
from typing import Any, Optional

from core.db import db, new_id, now_iso
from models import (
    GuidanceComparable, GuidanceResult, MarketAuditEvent, ValuationRequest,
)


# ---------------- helpers ----------------
def _norm(v: Optional[str]) -> str:
    return (v or "").strip().lower()


def _months_since(iso: Optional[str]) -> float:
    if not iso:
        return 999.0
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except Exception:
        return 999.0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - dt
    return delta.days / 30.4375


def _pct_diff(a, b) -> Optional[float]:
    if a is None or b is None or max(abs(a or 0), abs(b or 0)) == 0:
        return None
    return abs(a - b) / max(abs(a), abs(b)) * 100.0


def _size_factor(diff_pct, bands) -> float:
    if diff_pct is None:
        return 0.0
    for b in bands:
        if diff_pct <= float(b["max_diff_pct"]):
            return float(b["factor"])
    return 0.0


def _recency_factor(months: float, params: dict) -> float:
    if months <= float(params.get("current_months", 6)):
        return float(params.get("recency_0_6_factor", 1.00))
    if months <= float(params.get("relevant_months", 12)):
        return float(params.get("recency_7_12_factor", 0.80))
    if months <= float(params.get("historical_support_months", 24)):
        return float(params.get("recency_13_24_factor", 0.45))
    return 0.0


def _location_tier(subj: dict, cand: dict) -> tuple[str, float]:
    p = subj.get("_params") or {}
    if _norm(subj.get("street")) and _norm(subj["street"]) == _norm(cand.get("street")) \
            and _norm(subj.get("suburb")) == _norm(cand.get("suburb")):
        return "same_street", float(p.get("location_same_street_factor", 1.00))
    if _norm(subj.get("local_area")) and _norm(subj["local_area"]) == _norm(cand.get("local_area")) \
            and _norm(subj.get("suburb")) == _norm(cand.get("suburb")):
        return "same_local_area", float(p.get("location_same_local_area_factor", 0.90))
    if _norm(subj.get("suburb")) and _norm(subj["suburb"]) == _norm(cand.get("suburb")):
        return "same_suburb", float(p.get("location_same_suburb_factor", 0.75))
    return "supporting", 0.5


# ---------------- observation pool ----------------
async def _pool_observations(subject: dict, params: dict) -> list[dict]:
    """
    Return unified observation records:
    {
      master_id, source ("market" or "trel"), listing_id?, trel_property_id?,
      purpose, price, property_class, property_subtype, bedrooms, bathrooms,
      land_area_m2, building_area_m2, street, local_area, suburb, city, province,
      observation_date
    }
    Deduped by master_id, latest per purpose.
    """
    purpose = subject["purpose"]
    subj_class = subject.get("property_class")
    subj_suburb = _norm(subject.get("suburb"))

    seen: dict[str, dict] = {}

    # 1) Master properties with same class + same suburb (broad candidate pool)
    q_masters: dict[str, Any] = {}
    if subj_class:
        q_masters["property_class"] = subj_class
    if subj_suburb:
        q_masters["suburb"] = {"$regex": f"^{subject['suburb']}$", "$options": "i"}
    async for m in db.master_properties.find(q_masters, {"_id": 0}).limit(500):
        seen[m["id"]] = {"master": m, "obs": None}

    # 2) Latest market_listing per master for the same purpose
    if seen:
        master_ids = list(seen.keys())
        async for l in db.market_listings.find(
            {"purpose": purpose, "status": "active"}, {"_id": 0},
        ).sort("last_seen", -1):
            match = await db.property_matches.find_one(
                {"market_listing_id": l["id"], "status": "active",
                 "master_property_id": {"$in": master_ids}},
                {"_id": 0, "master_property_id": 1},
            )
            if not match:
                continue
            mid = match["master_property_id"]
            if seen.get(mid) and seen[mid]["obs"] is None:
                seen[mid]["obs"] = {
                    "source": "market", "listing_id": l["id"],
                    "price": l.get("price"), "purpose": l.get("purpose"),
                    "observation_date": l.get("last_seen"),
                }

    # 3) TREL property fallback (link via trel_property_id)
    for mid, entry in seen.items():
        if entry["obs"] is not None:
            continue
        trel_id = entry["master"].get("trel_property_id")
        if not trel_id:
            continue
        p = await db.properties.find_one({"id": trel_id}, {"_id": 0})
        if not p:
            continue
        if _norm(p.get("listing_type")) != purpose:
            continue
        entry["obs"] = {
            "source": "trel", "trel_property_id": trel_id,
            "price": p.get("price"), "purpose": p.get("listing_type"),
            "observation_date": p.get("updated_at") or p.get("created_at"),
            "bedrooms": p.get("bedrooms"), "bathrooms": p.get("bathrooms"),
            "land_area_m2": (p.get("total_area_ha") or 0) * 10000 or None,
        }

    # Assemble observations
    out = []
    for mid, entry in seen.items():
        if not entry["obs"] or not entry["obs"].get("price"):
            continue
        m = entry["master"]; o = entry["obs"]
        out.append({
            "master_id": mid,
            "source": o["source"],
            "listing_id": o.get("listing_id"),
            "trel_property_id": o.get("trel_property_id"),
            "purpose": o.get("purpose"),
            "price": float(o["price"]),
            "property_class": m.get("property_class"),
            "property_subtype": m.get("property_subtype"),
            "bedrooms": o.get("bedrooms") or m.get("bedrooms"),
            "bathrooms": o.get("bathrooms") or m.get("bathrooms"),
            "land_area_m2": o.get("land_area_m2") or m.get("land_area_m2"),
            "building_area_m2": m.get("building_area_m2"),
            "street": m.get("street"),
            "local_area": m.get("local_area"),
            "suburb": m.get("suburb"),
            "city": m.get("city"),
            "province": m.get("province"),
            "observation_date": o.get("observation_date"),
        })
    return out


# ---------------- CQS ----------------
def _cqs(subject: dict, cand: dict, params: dict) -> tuple[float, dict, str, float]:
    """Return (cqs, breakdown, tier, tier_factor)."""
    subj_view = {**subject, "_params": params}
    tier, tier_factor = _location_tier(subj_view, cand)

    cls = subject.get("property_class") or "residential"
    profile = params.get("cqs_baseline", {}).get(cls) \
              or params["cqs_baseline"]["residential"]

    breakdown = {"location": 0.0, "class_subtype": 0.0, "size": 0.0,
                 "features": 0.0, "condition": 0.0, "recency": 0.0}

    breakdown["location"] = float(profile["location"]) * tier_factor

    if _norm(subject.get("property_class")) == _norm(cand.get("property_class")):
        subtype_full = _norm(subject.get("property_subtype")) == _norm(cand.get("property_subtype"))
        breakdown["class_subtype"] = float(profile["class_subtype"]) * (1.0 if subtype_full else 0.6)

    bands = params.get("size_similarity_bands", [])
    if cls == "vacant_land":
        size_diff = _pct_diff(subject.get("land_area_m2"), cand.get("land_area_m2"))
    elif cls == "commercial_industrial":
        size_diff = _pct_diff(subject.get("building_area_m2"), cand.get("building_area_m2")) \
                    or _pct_diff(subject.get("land_area_m2"), cand.get("land_area_m2"))
    else:  # residential
        size_diff = _pct_diff(subject.get("building_area_m2"), cand.get("building_area_m2")) \
                    or _pct_diff(subject.get("land_area_m2"), cand.get("land_area_m2"))
    breakdown["size"] = float(profile["size"]) * _size_factor(size_diff, bands)

    # features (residential only): bedrooms + bathrooms
    if cls == "residential" and profile["features"]:
        f = 0.0
        if subject.get("bedrooms") is not None and cand.get("bedrooms") is not None:
            diff = abs(int(subject["bedrooms"]) - int(cand["bedrooms"]))
            f += (1.0 if diff == 0 else (0.6 if diff == 1 else 0.0)) * (10 / 17)
        if subject.get("bathrooms") is not None and cand.get("bathrooms") is not None:
            diff = abs(int(subject["bathrooms"]) - int(cand["bathrooms"]))
            f += (1.0 if diff == 0 else (0.5 if diff == 1 else 0.0)) * (5 / 17)
        breakdown["features"] = float(profile["features"]) * min(1.0, f + 0.1)

    # condition: partial credit when both known (Phase 1: assume same)
    breakdown["condition"] = float(profile["condition"]) * 0.6

    # recency
    months = _months_since(cand.get("observation_date"))
    recency_factor = _recency_factor(months, params)
    breakdown["recency"] = float(profile["recency"]) * recency_factor

    cqs = round(sum(breakdown.values()), 2)
    return cqs, breakdown, tier, tier_factor


# ---------------- outlier + statistics ----------------
def _iqr_filter(values: list[float], multiplier: float) -> tuple[list[float], list[float]]:
    if len(values) < 6:
        return values, []
    q1, q3 = statistics.quantiles(values, n=4)[0], statistics.quantiles(values, n=4)[2]
    iqr = q3 - q1
    low, high = q1 - multiplier * iqr, q3 + multiplier * iqr
    kept = [v for v in values if low <= v <= high]
    dropped = [v for v in values if v < low or v > high]
    return kept, dropped


def _weighted_median(values: list[float], weights: list[float]) -> Optional[float]:
    if not values or not weights or sum(weights) == 0:
        return None
    pairs = sorted(zip(values, weights))
    total = sum(w for _, w in pairs)
    cum = 0.0
    for v, w in pairs:
        cum += w
        if cum >= total / 2:
            return v
    return pairs[-1][0]


def _weighted_percentile(values: list[float], weights: list[float], pct: float) -> Optional[float]:
    if not values or not weights or sum(weights) == 0:
        return None
    pairs = sorted(zip(values, weights))
    total = sum(w for _, w in pairs)
    target = total * pct / 100.0
    cum = 0.0
    for v, w in pairs:
        cum += w
        if cum >= target:
            return v
    return pairs[-1][0]


# ---------------- Confidence ----------------
def _confidence(count: int, avg_cqs: float, recency_coverage: float,
                dispersion: float, params: dict) -> tuple[float, str]:
    """Return (score 0-100, label)."""
    w = params.get("confidence_weights", {"quantity": 30, "quality": 35,
                                           "recency": 20, "dispersion": 15})
    # quantity component: linear ramp 0→30 across 1..15 comps
    qty = min(1.0, count / 15.0)
    q_score = w["quantity"] * qty
    quality = w["quality"] * min(1.0, avg_cqs / 100.0)
    recency = w["recency"] * recency_coverage
    disp = w["dispersion"] * max(0.0, 1.0 - min(1.0, dispersion))
    total = round(q_score + quality + recency + disp, 2)

    # Gate + label
    if count <= 2:
        return total, "insufficient"
    if count <= int(params.get("limited_max_count", 5)):
        return total, "limited"
    if total >= 80 and count >= int(params.get("strong_min_count", 11)):
        return total, "strong"
    if total >= 60:
        return total, "moderate"
    if total >= 40:
        return total, "limited"
    return total, "insufficient"


# ---------------- public entry ----------------
async def generate_guidance(subject: dict, workflow: str = "admin",
                             actor_id: Optional[str] = None) -> dict:
    cfg = await db.market_configuration.find_one(
        {"active": True, "algorithm": {"$in": ["combined", "guidance"]}}, {"_id": 0},
    )
    if not cfg:
        raise RuntimeError("No active market configuration")
    params = cfg["parameters"]; version = cfg["version"]

    # Persist the request
    req = ValuationRequest(
        subject_property_id=subject.get("trel_property_id"),
        subject_master_property_id=subject.get("master_property_id"),
        subject_snapshot=subject, purpose=subject["purpose"],
        workflow=workflow, requestor_user_id=actor_id,
        algorithm_version="GUIDE-1.0", config_version=version,
    ).model_dump()
    await db.valuation_requests.insert_one(req)
    req.pop("_id", None)

    # Pool observations
    obs = await _pool_observations(subject, params)

    # Score each
    scored = []
    for o in obs:
        cqs, breakdown, tier, tier_factor = _cqs(subject, o, params)
        months = _months_since(o.get("observation_date"))
        recency = _recency_factor(months, params)
        eff = (cqs / 100.0) * recency * tier_factor
        scored.append({**o, "cqs": cqs, "cqs_breakdown": breakdown,
                       "tier": tier, "tier_factor": tier_factor,
                       "recency_factor": recency, "effective_weight": eff,
                       "months_since": round(months, 1)})

    usable = [s for s in scored if s["cqs"] >= float(params.get("quality_min_usable", 45))
              and s["effective_weight"] > 0]
    excluded_quality = [s for s in scored if s not in usable]

    values = [s["price"] for s in usable]
    kept_vals, dropped_vals = _iqr_filter(values, float(params.get("iqr_outlier_multiplier", 1.5)))
    kept_ids = set()
    included, outliers = [], []
    dropped_set = set(dropped_vals)
    for s in usable:
        if s["price"] in dropped_set and s["price"] not in kept_ids:
            outliers.append({**s, "inclusion_status": "excluded_outlier",
                             "exclusion_reason": "iqr_outlier"})
            dropped_set.remove(s["price"])
        else:
            included.append({**s, "inclusion_status": "included"})
            kept_ids.add(s["price"])

    included.sort(key=lambda s: (-s["cqs"], -s["recency_factor"]))

    # Stats
    prices = [s["price"] for s in included]
    weights = [s["effective_weight"] for s in included]
    observed_range = {"min": min(prices), "max": max(prices)} if prices else {}
    median_val = statistics.median(prices) if prices else None
    weighted_med = _weighted_median(prices, weights)

    lo_pct = float(params.get("indicative_lower_percentile", 25))
    hi_pct = float(params.get("indicative_upper_percentile", 75))
    trel_range = {}
    if len(included) >= int(params.get("min_direct_for_formal_range", 3)):
        p25 = _weighted_percentile(prices, weights, lo_pct)
        p75 = _weighted_percentile(prices, weights, hi_pct)
        if p25 is not None and p75 is not None:
            trel_range = {"p25": p25, "p75": p75}

    avg_cqs = statistics.fmean([s["cqs"] for s in included]) if included else 0.0
    current_count = sum(1 for s in included if s["months_since"] <= float(params.get("relevant_months", 12)))
    recency_coverage = current_count / len(included) if included else 0.0
    dispersion = 0.0
    if len(prices) >= 2 and weighted_med and weighted_med > 0:
        dispersion = statistics.pstdev(prices) / weighted_med
    conf_score, conf_label = _confidence(
        len(included), avg_cqs, recency_coverage, dispersion, params,
    )

    # Persist result + comparables
    result = GuidanceResult(
        valuation_request_id=req["id"],
        comparable_count=len(included),
        observed_range=observed_range,
        median=median_val, weighted_median=weighted_med,
        trel_indicative_range=trel_range,
        confidence_score=conf_score, confidence_label=conf_label,
        supporting_evidence_count=0,
        outputs={"workflow": workflow, "subject": subject,
                 "avg_cqs": round(avg_cqs, 2)},
        algorithm_version="GUIDE-1.0", config_version=version,
    ).model_dump()
    await db.guidance_results.insert_one(result)
    result.pop("_id", None)

    comp_docs = []
    for s in included + outliers + excluded_quality:
        cd = GuidanceComparable(
            guidance_result_id=result["id"],
            master_property_id=s["master_id"],
            market_listing_id=s.get("listing_id"),
            tier=s["tier"], quality_score=s["cqs"],
            recency_factor=s["recency_factor"],
            effective_weight=s["effective_weight"],
            value=s["price"],
            inclusion_status=s.get("inclusion_status") or (
                "excluded_quality" if s in excluded_quality else "included"
            ),
            exclusion_reason=s.get("exclusion_reason"),
            cqs_breakdown=s.get("cqs_breakdown") or {},
            months_since=s.get("months_since"),
        ).model_dump()
        await db.guidance_comparables.insert_one(cd)
        cd.pop("_id", None)
        comp_docs.append(cd)

    await db.market_audit_events.insert_one(
        MarketAuditEvent(
            event_type="guidance_run", actor_id=actor_id,
            entity_type="guidance_result", entity_id=result["id"],
            payload={"count": len(included), "confidence": conf_label,
                     "workflow": workflow},
            algorithm_version="GUIDE-1.0", config_version=version,
        ).model_dump()
    )

    return {"request": req, "result": result, "comparables": comp_docs}
