"""Duplicate Matching engine — MATCH-1.0 (spec-verbatim).

Public entry: `ingest_market_listing(payload, actor_id=None)`
  1. Load active config
  2. Upsert Market Listing (by (source_id, source_listing_id))
  3. Generate candidate Master Properties
  4. Apply Deterministic rules D1–D6
  5. Fallback: weighted 100-point scoring
  6. Decision band → auto-attach, review case, or new master
  7. Emit audit event
Returns the resulting {listing, match, review_case} triple.
"""
from __future__ import annotations

import math
from typing import Any, Optional

from core.db import db, new_id, now_iso
from models import (
    MarketAuditEvent, MarketListing, MarketReviewCase, MasterProperty,
    PropertyMatch,
)

# ---------------- helpers ----------------
def _norm(v: Optional[str]) -> str:
    return (v or "").strip().lower()


def _pct_diff(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None or (a == 0 and b == 0):
        return None
    if max(abs(a), abs(b)) == 0:
        return 0.0
    return abs(a - b) / max(abs(a), abs(b)) * 100.0


def _haversine_m(la1, lo1, la2, lo2) -> Optional[float]:
    if None in (la1, lo1, la2, lo2):
        return None
    R = 6371000.0
    p1, p2 = math.radians(la1), math.radians(la2)
    dp = math.radians(la2 - la1); dl = math.radians(lo2 - lo1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(min(1.0, math.sqrt(a)))


# ---------------- config ----------------
async def _load_active_config() -> dict:
    doc = await db.market_configuration.find_one(
        {"active": True, "algorithm": {"$in": ["combined", "match"]}},
        {"_id": 0},
    )
    if not doc:
        raise RuntimeError("No active market configuration")
    return doc


# ---------------- Stage 1: upsert source listing ----------------
async def _upsert_listing(payload: dict) -> tuple[dict, bool]:
    """Return (listing_doc, is_new). Dedupe by (source_id, source_listing_id)."""
    existing = await db.market_listings.find_one(
        {"source_id": payload["source_id"], "source_listing_id": payload["source_listing_id"]},
        {"_id": 0},
    )
    if existing:
        # Update last_seen, refresh mutable fields; store snapshot if price changed
        prev_price = existing.get("price")
        patch = {"last_seen": now_iso(), "updated_at": now_iso()}
        for k in ("price", "rent_period", "status", "source_url", "purpose",
                  "property_class", "property_subtype", "bedrooms", "bathrooms",
                  "land_area_m2", "building_area_m2", "allotment_number", "section_number",
                  "portion_number", "street", "suburb", "local_area", "city",
                  "province", "latitude", "longitude", "gps_accuracy"):
            if k in payload and payload[k] is not None:
                patch[k] = payload[k]
        if "price" in patch and patch["price"] != prev_price:
            await db.market_listing_snapshots.insert_one({
                "id": new_id(), "market_listing_id": existing["id"],
                "observed_at": now_iso(), "price": patch["price"],
                "rent_period": patch.get("rent_period") or existing.get("rent_period"),
                "status": patch.get("status") or existing.get("status"),
                "raw_snapshot": {"prev_price": prev_price},
            })
        await db.market_listings.update_one({"id": existing["id"]}, {"$set": patch})
        return {**existing, **patch}, False

    listing = MarketListing(**payload).model_dump()
    await db.market_listings.insert_one(listing)
    listing.pop("_id", None)
    if listing.get("price") is not None:
        await db.market_listing_snapshots.insert_one({
            "id": new_id(), "market_listing_id": listing["id"],
            "observed_at": listing["first_seen"], "price": listing["price"],
            "rent_period": listing.get("rent_period"),
            "status": listing.get("status"),
            "raw_snapshot": {"origin": "first_seen"},
        })
    return listing, True


# ---------------- Stage 2: candidate generation ----------------
async def _candidates(listing: dict) -> list[dict]:
    """Bounded set of plausible master properties."""
    qs = []
    # Priority 1: allotment + section + suburb
    if listing.get("allotment_number") and listing.get("section_number") and listing.get("suburb"):
        qs.append({
            "allotment_number": listing["allotment_number"],
            "section_number": listing["section_number"],
            "suburb": listing["suburb"],
        })
    # Priority 2: allotment + section + street (suburb missing)
    if listing.get("allotment_number") and listing.get("section_number") and listing.get("street"):
        qs.append({
            "allotment_number": listing["allotment_number"],
            "section_number": listing["section_number"],
            "street": listing["street"],
        })
    # Priority 3: street + suburb
    if listing.get("street") and listing.get("suburb"):
        qs.append({"street": listing["street"], "suburb": listing["suburb"]})
    # Priority 4: portion + city/province
    if listing.get("portion_number") and (listing.get("city") or listing.get("province")):
        qs.append({
            "portion_number": listing["portion_number"],
            **({"city": listing["city"]} if listing.get("city") else {}),
            **({"province": listing["province"]} if listing.get("province") else {}),
        })
    # Priority 5: same suburb (broad — bounded)
    if listing.get("suburb"):
        qs.append({"suburb": listing["suburb"]})

    seen = set()
    out = []
    for q in qs:
        async for m in db.master_properties.find(q, {"_id": 0}).limit(30):
            if m["id"] not in seen:
                seen.add(m["id"])
                out.append(m)
        if len(out) >= 50:
            break
    return out


# ---------------- Stage 3: Deterministic Rules ----------------
def _hard_conflicts(listing: dict, master: dict, cfg: dict) -> list[str]:
    conflicts = []
    # Class mismatch on strong evidence: vacant vs improved
    lc, mc = listing.get("property_class"), master.get("property_class")
    if lc and mc and (
        (lc == "vacant_land") != (mc == "vacant_land")
    ):
        conflicts.append("class_vacant_vs_improved")

    # Different allotment on same section+suburb → different parcel
    if (listing.get("allotment_number") and master.get("allotment_number")
            and _norm(listing["allotment_number"]) != _norm(master["allotment_number"])
            and listing.get("section_number") and master.get("section_number")
            and _norm(listing["section_number"]) == _norm(master["section_number"])
            and listing.get("suburb") and master.get("suburb")
            and _norm(listing["suburb"]) == _norm(master["suburb"])):
        conflicts.append("allotment_conflict")

    # Different suburb on same street — could be alias but flag
    if (listing.get("suburb") and master.get("suburb")
            and _norm(listing["suburb"]) != _norm(master["suburb"])
            and listing.get("street") and master.get("street")
            and _norm(listing["street"]) == _norm(master["street"])):
        conflicts.append("suburb_conflict")

    # GPS beyond conflict threshold
    dist = _haversine_m(listing.get("latitude"), listing.get("longitude"),
                        master.get("latitude"), master.get("longitude"))
    if dist is not None and dist > float(cfg["parameters"].get("exact_gps_conflict_m", 500)):
        conflicts.append("gps_conflict")

    return conflicts


def _apply_deterministic(listing: dict, master: dict, cfg: dict) -> Optional[str]:
    """Return rule id (D1..D6) if it applies, else None."""
    conflicts = _hard_conflicts(listing, master, cfg)
    if conflicts:
        return None

    # D6 — direct TREL link
    if listing.get("trel_property_id") and master.get("trel_property_id") \
            and listing["trel_property_id"] == master["trel_property_id"]:
        return "D6"

    lot = _norm(listing.get("allotment_number")); msec = _norm(listing.get("section_number"))
    street = _norm(listing.get("street")); suburb = _norm(listing.get("suburb"))
    mlot = _norm(master.get("allotment_number")); msec2 = _norm(master.get("section_number"))
    mstreet = _norm(master.get("street")); msuburb = _norm(master.get("suburb"))

    # D1 — exact allotment + section + street + suburb
    if lot and msec and street and suburb and lot == mlot and msec == msec2 \
            and street == mstreet and suburb == msuburb:
        return "D1"

    # D2 — exact allotment + section + suburb, street missing/absent
    if lot and msec and suburb and lot == mlot and msec == msec2 and suburb == msuburb \
            and (not street or not mstreet):
        return "D2"

    # D3 — unit + building + parent (approx: same building name + same suburb)
    if listing.get("building_name") and master.get("building_name") \
            and _norm(listing["building_name"]) == _norm(master["building_name"]) \
            and suburb and suburb == msuburb:
        return "D3"

    # D4 — vacant land, same lot+section+suburb, both vacant
    if lot and msec and suburb and lot == mlot and msec == msec2 and suburb == msuburb \
            and listing.get("property_class") == "vacant_land" \
            and master.get("property_class") == "vacant_land":
        return "D4"

    # D5 — same portion + locality/district/province
    lp = _norm(listing.get("portion_number")); mp = _norm(master.get("portion_number"))
    if lp and mp and lp == mp \
            and _norm(listing.get("city")) == _norm(master.get("city")):
        return "D5"

    return None


# ---------------- Stage 4: Weighted Scoring ----------------
def _size_factor(diff_pct: Optional[float], bands: list[dict]) -> float:
    if diff_pct is None:
        return 0.0
    for b in bands:
        if diff_pct <= float(b["max_diff_pct"]):
            return float(b["factor"])
    return 0.0


def _weighted_score(listing: dict, master: dict, cfg: dict) -> tuple[float, dict, list[str]]:
    """Return (score, signals, conflicts). Signals is per-signal contribution."""
    params = cfg["parameters"]
    weights = params.get("signal_weights", {})
    sig: dict[str, float] = {}
    conflicts = _hard_conflicts(listing, master, cfg)

    def add(name: str, ok: bool, weight_key: Optional[str] = None,
            factor: float = 1.0) -> None:
        w = weights.get(weight_key or name, 0)
        sig[name] = float(w) * factor if ok else 0.0

    # exact matches on strong identifiers
    add("allotment_number", _norm(listing.get("allotment_number")) != "" and
        _norm(listing.get("allotment_number")) == _norm(master.get("allotment_number")))
    add("section_number", _norm(listing.get("section_number")) != "" and
        _norm(listing.get("section_number")) == _norm(master.get("section_number")))
    add("street", _norm(listing.get("street")) != "" and
        _norm(listing.get("street")) == _norm(master.get("street")))
    add("suburb", _norm(listing.get("suburb")) != "" and
        _norm(listing.get("suburb")) == _norm(master.get("suburb")))
    add("local_area", _norm(listing.get("local_area")) != "" and
        _norm(listing.get("local_area")) == _norm(master.get("local_area")))

    # size similarity (banded)
    bands = params.get("size_similarity_bands", [])
    land_diff = _pct_diff(listing.get("land_area_m2"), master.get("land_area_m2"))
    add("land_area", land_diff is not None, weight_key="land_area",
        factor=_size_factor(land_diff, bands))
    bldg_diff = _pct_diff(listing.get("building_area_m2"), master.get("building_area_m2"))
    add("building_area", bldg_diff is not None, weight_key="building_area",
        factor=_size_factor(bldg_diff, bands))

    add("property_class", _norm(listing.get("property_class")) != "" and
        _norm(listing.get("property_class")) == _norm(master.get("property_class")))
    add("property_subtype", _norm(listing.get("property_subtype")) != "" and
        _norm(listing.get("property_subtype")) == _norm(master.get("property_subtype")))

    # gps proximity (support only)
    dist = _haversine_m(listing.get("latitude"), listing.get("longitude"),
                        master.get("latitude"), master.get("longitude"))
    if dist is not None:
        support_m = float(params.get("exact_gps_support_m", 100))
        sig["gps"] = float(weights.get("gps", 0)) * (1.0 if dist <= support_m else 0.0)
    else:
        sig["gps"] = 0.0

    total = sum(sig.values())
    # Conflict penalty — subtract 30 per hard conflict, cap at 0
    total = max(0.0, total - 30.0 * len(conflicts))
    total = min(100.0, total)
    return total, sig, conflicts


# ---------------- Decision + persistence ----------------
def _decision_band(score: float, method: str, conflicts: list[str], params: dict) -> str:
    if conflicts:
        return "conflict_review"
    if method in ("D1", "D2", "D3", "D4", "D5", "D6") and score >= float(params.get("certain_min_score", 95)):
        return "certain"
    if score >= float(params.get("auto_match_threshold", 90)):
        return "automatic"
    if score >= float(params.get("probable_threshold", 75)):
        return "probable"
    if score >= float(params.get("possible_threshold", 55)):
        return "possible"
    return "no_match"


async def _emit_audit(event_type: str, actor_id: Optional[str], **kwargs) -> None:
    ev = MarketAuditEvent(event_type=event_type, actor_id=actor_id, **kwargs).model_dump()
    await db.market_audit_events.insert_one(ev)


async def _create_master_from_listing(listing: dict) -> dict:
    m = MasterProperty(
        property_class=listing.get("property_class"),
        property_subtype=listing.get("property_subtype"),
        allotment_number=listing.get("allotment_number"),
        section_number=listing.get("section_number"),
        portion_number=listing.get("portion_number"),
        street=listing.get("street"),
        suburb=listing.get("suburb"),
        local_area=listing.get("local_area"),
        city=listing.get("city"),
        province=listing.get("province"),
        latitude=listing.get("latitude"),
        longitude=listing.get("longitude"),
        land_area_m2=listing.get("land_area_m2"),
        building_area_m2=listing.get("building_area_m2"),
        is_vacant=(listing.get("property_class") == "vacant_land"),
        canonical_fields={"provenance": "matcher_new_master",
                          "source_listing_id": listing["id"]},
    ).model_dump()
    await db.master_properties.insert_one(m)
    m.pop("_id", None)
    return m


async def ingest_market_listing(payload: dict, actor_id: Optional[str] = None) -> dict:
    """End-to-end pipeline. Returns rich result dict for UI."""
    cfg = await _load_active_config()
    params = cfg["parameters"]
    version = cfg["version"]

    listing, is_new = await _upsert_listing(payload)

    # Skip matching if listing has no price (per spec eligibility)
    if listing.get("price") is None:
        await db.market_listings.update_one(
            {"id": listing["id"]},
            {"$set": {"status": "excluded", "exclusion_reason": "no_price"}},
        )
        return {"listing": listing, "match": None, "review_case": None,
                "excluded": True, "reason": "no_price"}

    candidates = await _candidates(listing)

    # Try deterministic against every candidate
    best_det: Optional[tuple[str, dict]] = None
    for m in candidates:
        rule = _apply_deterministic(listing, m, cfg)
        if rule:
            best_det = (rule, m); break

    # If deterministic hit → certain match
    match_doc = None; review_doc = None
    if best_det:
        rule, master = best_det
        score = 100.0
        signals = {"deterministic_rule": rule}
        band = _decision_band(score, rule, [], params)
        match_doc = PropertyMatch(
            market_listing_id=listing["id"], master_property_id=master["id"],
            method=rule, decision_band=band, score=score, signals=signals,
            algorithm_version="MATCH-1.0", config_version=version, status="active",
        ).model_dump()
        await db.property_matches.insert_one(match_doc)
        match_doc.pop("_id", None)
        await _emit_audit("match_created", actor_id, entity_type="property_match",
                          entity_id=match_doc["id"],
                          payload={"method": rule, "band": band, "score": score,
                                   "master_property_id": master["id"]},
                          algorithm_version="MATCH-1.0", config_version=version)
    else:
        # Weighted scoring across all candidates
        scored = []
        for m in candidates:
            s, sig, conf = _weighted_score(listing, m, cfg)
            scored.append((s, sig, conf, m))
        scored.sort(key=lambda x: x[0], reverse=True)

        if scored and scored[0][0] >= float(params.get("possible_threshold", 55)):
            top_score, top_sig, top_conf, top_master = scored[0]
            band = _decision_band(top_score, "weighted", top_conf, params)

            if band in ("automatic", "certain"):
                match_doc = PropertyMatch(
                    market_listing_id=listing["id"],
                    master_property_id=top_master["id"],
                    method="weighted", decision_band=band, score=top_score,
                    signals=top_sig, conflicts=top_conf,
                    algorithm_version="MATCH-1.0", config_version=version,
                    status="active",
                ).model_dump()
                await db.property_matches.insert_one(match_doc)
                match_doc.pop("_id", None)
                await _emit_audit("match_created", actor_id, entity_type="property_match",
                                  entity_id=match_doc["id"],
                                  payload={"method": "weighted", "band": band,
                                           "score": top_score,
                                           "master_property_id": top_master["id"]},
                                  algorithm_version="MATCH-1.0", config_version=version)
            else:
                # Probable / possible / conflict → review case
                case_type = "conflict" if band == "conflict_review" else band
                review_doc = MarketReviewCase(
                    case_type=case_type,
                    market_listing_id=listing["id"],
                    proposed_master_property_id=top_master["id"],
                    score=top_score, conflicts=top_conf,
                    payload={"signals": top_sig, "band": band,
                             "other_candidates": [
                                 {"master_id": c[3]["id"], "score": c[0]}
                                 for c in scored[1:6]
                             ]},
                    status="open",
                ).model_dump()
                await db.market_review_cases.insert_one(review_doc)
                review_doc.pop("_id", None)
                await _emit_audit("review_case_created", actor_id,
                                  entity_type="market_review_case",
                                  entity_id=review_doc["id"],
                                  payload={"band": band, "score": top_score,
                                           "listing_id": listing["id"]},
                                  algorithm_version="MATCH-1.0", config_version=version)
        else:
            # No sufficient match → mint a new Master Property
            new_master = await _create_master_from_listing(listing)
            match_doc = PropertyMatch(
                market_listing_id=listing["id"],
                master_property_id=new_master["id"],
                method="weighted", decision_band="automatic",
                score=100.0, signals={"reason": "new_master_created"},
                algorithm_version="MATCH-1.0", config_version=version, status="active",
            ).model_dump()
            await db.property_matches.insert_one(match_doc)
            match_doc.pop("_id", None)
            await _emit_audit("master_created", actor_id,
                              entity_type="master_property",
                              entity_id=new_master["id"],
                              payload={"from_listing": listing["id"]},
                              algorithm_version="MATCH-1.0", config_version=version)

    return {"listing": listing, "match": match_doc, "review_case": review_doc,
            "candidates_considered": len(candidates), "is_new": is_new}


async def rematch_listing(listing_id: str, actor_id: Optional[str] = None) -> dict:
    """Detach any active match for this listing and re-run the matcher."""
    listing = await db.market_listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        raise ValueError("Listing not found")
    await db.property_matches.update_many(
        {"market_listing_id": listing_id, "status": "active"},
        {"$set": {"status": "superseded", "updated_at": now_iso()}},
    )
    return await ingest_market_listing(listing, actor_id=actor_id)
