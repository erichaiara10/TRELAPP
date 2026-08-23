"""Fast, deterministic price guidance from TREL and external market evidence."""
from __future__ import annotations

import asyncio
import re
import statistics
from typing import Any, Dict, List, Optional


ACTIVE_INTERNAL = {"active", "under_offer"}
ACTIVE_EXTERNAL = {"ACTIVE", "RELISTED", "SOLD_CONFIRMED", "RENTED_CONFIRMED"}


def _exact(value: str) -> Dict[str, Any]:
    return {"$regex": f"^{re.escape(value.strip())}$", "$options": "i"}


def _strength(count: int) -> str:
    if count < 3:
        return "INSUFFICIENT"
    if count <= 5:
        return "LIMITED"
    if count <= 10:
        return "MODERATE"
    return "STRONG"


def _score(row: Dict[str, Any], subject: Dict[str, Any]) -> int:
    score = 0
    if row.get("property_type_id") and row.get("property_type_id") == subject.get("property_type_id"):
        score += 35
    if row.get("suburb_id") and row.get("suburb_id") == subject.get("suburb_id"):
        score += 30
    elif row.get("city_id") and row.get("city_id") == subject.get("city_id"):
        score += 15
    if subject.get("local_area_id") and row.get("local_area_id") == subject.get("local_area_id"):
        score += 20
    elif subject.get("local_area") and str(row.get("local_area") or "").casefold() == str(subject["local_area"]).casefold():
        score += 20
    if subject.get("bedrooms") is not None and row.get("bedrooms") is not None:
        score += max(0, 20 - abs(int(row["bedrooms"]) - int(subject["bedrooms"])) * 8)
    if subject.get("bathrooms") is not None and row.get("bathrooms") is not None:
        score += max(0, 10 - abs(int(row["bathrooms"]) - int(subject["bathrooms"])) * 4)
    if subject.get("parking") is not None and row.get("parking") is not None:
        score += max(0, 5 - abs(int(row["parking"]) - int(subject["parking"])) * 2)
    for field in ("land_area_sqm", "building_area_sqm"):
        wanted, actual = subject.get(field), row.get(field)
        if wanted and actual:
            ratio = min(float(wanted), float(actual)) / max(float(wanted), float(actual))
            score += round(ratio * 20)
    if subject.get("property_condition") and str(row.get("property_condition") or "").casefold() == str(subject["property_condition"]).casefold():
        score += 5
    if subject.get("tenure_type") and str(row.get("tenure_type") or "").casefold() == str(subject["tenure_type"]).casefold():
        score += 5
    if subject.get("street_name") and str(row.get("street_name") or "").casefold() == str(subject["street_name"]).casefold():
        score += 10
    if subject.get("nearby_landmark") and str(row.get("nearby_landmark") or "").casefold() == str(subject["nearby_landmark"]).casefold():
        score += 5
    return score


class ComparableEvidenceService:
    """Read the two approved evidence groups without creating a merged table."""

    def __init__(self, database):
        self.db = database

    async def _subject(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        property_type, city, suburb, local_area = await asyncio.gather(
            self.db.property_types.find_one({"name": _exact(payload["property_type"])}, {"_id": 0, "id": 1}),
            self.db.cities.find_one({"name": _exact(payload.get("city") or "")}, {"_id": 0, "id": 1}),
            self.db.suburbs.find_one({"name": _exact(payload.get("suburb") or "")}, {"_id": 0, "id": 1, "city_id": 1}),
            self.db.local_areas.find_one({"name": _exact(payload.get("local_area") or "")}, {"_id": 0, "id": 1}),
        )
        return {
            **payload,
            "property_type_id": (property_type or {}).get("id"),
            "city_id": (city or {}).get("id") or (suburb or {}).get("city_id"),
            "suburb_id": (suburb or {}).get("id"),
            "local_area_id": (local_area or {}).get("id"),
        }

    async def _internal(self, subject: Dict[str, Any]) -> List[Dict[str, Any]]:
        address_query: Dict[str, Any] = {"is_canonical": True, "valid_to": None}
        if subject.get("suburb_id"):
            address_query["suburb_id"] = subject["suburb_id"]
        elif subject.get("suburb"):
            address_query["suburb_name"] = _exact(subject["suburb"])
        elif subject.get("city_id"):
            address_query["city_id"] = subject["city_id"]
        else:
            address_query["city_name"] = _exact(subject["city"])
        addresses = await self.db.property_addresses.find(address_query, {"_id": 0}).limit(500).to_list(500)
        address_by_id = {row["property_id"]: row for row in addresses}
        property_ids = list(address_by_id)
        if not property_ids:
            return []
        master_query: Dict[str, Any] = {"id": {"$in": property_ids}, "lifecycle_status": {"$ne": "deleted"}}
        if subject.get("property_type_id"):
            master_query["property_type_id"] = subject["property_type_id"]
        else:
            master_query["property_type_name"] = _exact(subject["property_type"])
        masters = await self.db.master_properties.find(master_query, {"_id": 0, "id": 1, "property_type_id": 1, "property_type_name": 1}).to_list(500)
        master_by_id = {row["id"]: row for row in masters}
        if not master_by_id:
            return []
        listing_query = {
            "property_id": {"$in": list(master_by_id)},
            "transaction_type": subject["listing_type"].upper(),
            "publication_status": {"$in": list(ACTIVE_INTERNAL)},
            "price_current": {"$gt": 0},
        }
        listings = await self.db.listings.find(listing_query, {"_id": 0}).sort("created_at", -1).limit(300).to_list(300)
        attrs, parcels = await asyncio.gather(
            self.db.property_attributes.find({"property_id": {"$in": list(master_by_id)}}, {"_id": 0}).to_list(500),
            self.db.property_parcels.find({"property_id": {"$in": list(master_by_id)}}, {"_id": 0}).to_list(500),
        )
        attr_by_id = {row["property_id"]: row for row in attrs}
        parcel_by_id = {row["property_id"]: row for row in parcels}
        output, seen = [], set()
        for listing in listings:
            pid = listing["property_id"]
            if pid in seen or pid == subject.get("property_id"):
                continue
            seen.add(pid)
            master, address, attr = master_by_id[pid], address_by_id[pid], attr_by_id.get(pid, {})
            parcel = parcel_by_id.get(pid, {})
            type_name = str(master.get("property_type_name") or "").casefold()
            generic_area = attr.get("area_sqm")
            output.append({
                "dedupe_key": f"property:{pid}", "master_property_id": pid,
                "evidence_group": "TREL_INTERNAL", "source_name": "TRELPNG",
                "title": listing.get("title") or master.get("property_type_name") or "TREL property",
                "property_type": master.get("property_type_name"), "property_type_id": master.get("property_type_id"),
                "suburb": address.get("suburb_name"), "suburb_id": address.get("suburb_id"),
                "city": address.get("city_name"), "city_id": address.get("city_id"),
                "local_area": address.get("local_area_name"), "local_area_id": address.get("local_area_id"),
                "street_name": address.get("street_name"), "nearby_landmark": address.get("nearby_landmark"),
                "bedrooms": attr.get("bedrooms"), "bathrooms": attr.get("bathrooms"),
                "parking": attr.get("parking"),
                "land_area_sqm": (float(parcel["area_hectares"]) * 10000 if parcel.get("area_hectares") else generic_area if "land" in type_name else None),
                "building_area_sqm": (generic_area if any(x in type_name for x in ("commercial", "industrial", "office", "warehouse", "retail")) else None),
                "property_condition": attr.get("property_condition") or attr.get("condition"),
                "tenure_type": parcel.get("tenure_type"), "price": float(listing["price_current"]),
                "observed_at": listing.get("updated_at") or listing.get("created_at"),
            })
        return output

    async def _external(self, subject: Dict[str, Any]) -> List[Dict[str, Any]]:
        query: Dict[str, Any] = {
            "transaction_type": subject["listing_type"].upper(),
            "priced_usable": True, "comparable_eligible": True,
            "status": {"$in": list(ACTIVE_EXTERNAL)},
        }
        refinements = []
        if subject.get("property_type_id"):
            refinements.append({"$or": [
                {"property_type_id": subject["property_type_id"]},
                {"property_type_name": _exact(subject["property_type"])},
            ]})
        else:
            query["property_type_name"] = _exact(subject["property_type"])
        if subject.get("suburb_id"):
            refinements.append({"$or": [
                {"suburb_id": subject["suburb_id"]},
                {"suburb_name": _exact(subject["suburb"])},
            ]})
        elif subject.get("suburb"):
            query["suburb_name"] = _exact(subject["suburb"])
        elif subject.get("city_id"):
            query["city_id"] = subject["city_id"]
        else:
            query["city_name"] = _exact(subject["city"])
        if refinements:
            query["$and"] = refinements
        observations = await self.db.source_listing_observations.find(query, {"_id": 0}).sort("observed_at", -1).limit(500).to_list(500)
        latest: Dict[str, Dict[str, Any]] = {}
        for row in observations:
            latest.setdefault(row["source_listing_id"], row)
        rows = list(latest.values())
        if not rows:
            return []
        obs_ids = [row["id"] for row in rows]
        source_listing_ids = list(latest)
        prices, source_listings = await asyncio.gather(
            self.db.observation_prices.find({"observation_id": {"$in": obs_ids}}, {"_id": 0}).to_list(len(obs_ids)),
            self.db.source_listings.find({"id": {"$in": source_listing_ids}}, {"_id": 0}).to_list(len(source_listing_ids)),
        )
        price_by_obs = {row["observation_id"]: row for row in prices}
        listing_by_id = {row["id"]: row for row in source_listings}
        site_ids = list({row.get("source_site_id") for row in source_listings if row.get("source_site_id")})
        sites = await self.db.source_sites.find({"id": {"$in": site_ids}}, {"_id": 0, "id": 1, "name": 1}).to_list(len(site_ids)) if site_ids else []
        site_by_id = {row["id"]: row for row in sites}
        output = []
        for obs in rows:
            listing = listing_by_id.get(obs["source_listing_id"], {})
            price = price_by_obs.get(obs["id"], {})
            amount = price.get("monthly_equivalent") if subject["listing_type"] == "rent" else price.get("amount")
            if not isinstance(amount, (int, float)) or amount <= 0:
                continue
            output.append({
                "dedupe_key": f"property:{listing['master_property_id']}" if listing.get("master_property_id") else f"source:{obs['source_listing_id']}",
                "master_property_id": listing.get("master_property_id"),
                "evidence_group": "EXTERNAL_MARKET",
                "source_name": site_by_id.get(listing.get("source_site_id"), {}).get("name") or "External market",
                "title": obs.get("property_type_name") or "Comparable property",
                "property_type": obs.get("property_type_name"), "property_type_id": obs.get("property_type_id"),
                "suburb": obs.get("suburb_name"), "suburb_id": obs.get("suburb_id"),
                "city": obs.get("city_name"), "city_id": obs.get("city_id"),
                "local_area": obs.get("local_area_name"), "local_area_id": obs.get("local_area_id"),
                "street_name": obs.get("street_name"), "bedrooms": obs.get("bedrooms"),
                "bathrooms": obs.get("bathrooms"),
                "parking": obs.get("parking") or (obs.get("raw_payload") or {}).get("parking"),
                "land_area_sqm": obs.get("land_area_sqm"), "building_area_sqm": obs.get("building_area_sqm"),
                "property_condition": obs.get("property_condition") or (obs.get("raw_payload") or {}).get("property_condition") or (obs.get("raw_payload") or {}).get("condition"),
                "tenure_type": obs.get("tenure_type") or (obs.get("raw_payload") or {}).get("tenure_type"),
                "price": float(amount), "observed_at": obs.get("observed_at"),
            })
        return output

    async def analyse(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        subject = await self._subject(payload)
        internal, external = await asyncio.gather(self._internal(subject), self._external(subject))
        combined: Dict[str, Dict[str, Any]] = {}
        for row in internal + external:
            row["match_score"] = _score(row, subject)
            existing = combined.get(row["dedupe_key"])
            if existing is None or row["evidence_group"] == "TREL_INTERNAL":
                combined[row["dedupe_key"]] = row
        ranked = sorted(
            combined.values(),
            key=lambda row: (row["match_score"], str(row.get("observed_at") or "")),
            reverse=True,
        )
        usable = ranked[:100]
        prices = [row["price"] for row in usable]
        count = len(prices)
        strength = _strength(count)
        formal = count >= 3
        median = statistics.median(prices) if prices else 0
        if formal:
            ordered = sorted(prices)
            quartiles = statistics.quantiles(ordered, n=4, method="inclusive")
            q1, q3 = quartiles[0], quartiles[2]
            iqr = q3 - q1
            filtered = [p for p in ordered if p >= q1 - 1.5 * iqr and p <= q3 + 1.5 * iqr] or ordered
            range_min, range_max = min(filtered), max(filtered)
            average = statistics.mean(filtered)
            verdict = "overpriced" if payload["price"] > average * 1.10 else "underpriced" if payload["price"] < average * 0.90 else "fair"
        else:
            range_min = range_max = None
            average = median
            verdict = "insufficient"
        public = [{k: row.get(k) for k in ("title", "property_type", "suburb", "price", "evidence_group", "source_name", "match_score", "observed_at")} for row in usable[:10]]
        return {
            "range_min": range_min, "range_max": range_max, "average": average,
            "median": median, "verdict": verdict, "formal_range_available": formal,
            "evidence_strength": strength, "sample_size": count,
            "internal_count": sum(1 for row in usable if row["evidence_group"] == "TREL_INTERNAL"),
            "external_count": sum(1 for row in usable if row["evidence_group"] == "EXTERNAL_MARKET"),
            "comparables": public,
            "recommendation": "Insufficient comparable evidence for a formal TREL range." if not formal else "Calculated from deduplicated TREL and external market evidence.",
        }
