"""Canonical bridge between market observations and advertised Properties.

External source listings never create an advertised Property. They retain their
own history and either link to one existing Master Property, remain unmatched,
or enter a staff review queue when the identity evidence is ambiguous.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from core.db import new_id, now_iso
from core.integrated_property_service import norm


REAPPEARANCE_STATUSES = {"NOT_SEEN", "REMOVED", "UNKNOWN"}
TREL_DOMAINS = {"trelpng.com", "www.trelpng.com"}
MONTHLY_MULTIPLIERS = {
    "DAY": 365.25 / 12,
    "WEEK": 52 / 12,
    "FORTNIGHT": 26 / 12,
    "MONTH": 1,
    "YEAR": 1 / 12,
}


def monthly_equivalent(amount: float, transaction_type: str, rental_period: Optional[str]) -> Optional[float]:
    if transaction_type != "RENT":
        return None
    return round(float(amount) * MONTHLY_MULTIPLIERS.get(rental_period or "MONTH", 1), 2)


def effective_status(previous: Optional[str], incoming: str) -> str:
    if incoming == "ACTIVE" and previous in REAPPEARANCE_STATUSES:
        return "RELISTED"
    return incoming


def origin_kind(source: Dict[str, Any]) -> str:
    domain = str(source.get("domain") or "").lower().removeprefix("www.")
    return "TREL_OWN" if source.get("is_trel_owned") or domain in {"trelpng.com"} else "EXTERNAL"


def parcel_signature(payload: Dict[str, Any]) -> Tuple[Optional[str], Dict[str, Any]]:
    """Return the approved strong parcel scheme and normalized identifiers."""
    if payload.get("lot") and payload.get("section"):
        return "URBAN_LOT_SECTION", {
            "lot_norm": norm(payload.get("lot")),
            "section_norm": norm(payload.get("section")),
            "street_norm": norm(payload.get("street_name")),
        }
    if payload.get("portion"):
        return "PORTION", {
            "portion_norm": norm(payload.get("portion")),
            "location_norm": norm(payload.get("location_name") or payload.get("city_name")),
        }
    return None, {}


def collector_payload(source_site_id: str, row: Dict[str, Any]) -> Dict[str, Any]:
    """Translate a collector record into the integrated observation contract."""
    purpose = str(row.get("purpose") or "").upper()
    period = {
        "daily": "DAY", "day": "DAY", "weekly": "WEEK", "week": "WEEK",
        "fortnightly": "FORTNIGHT", "fortnight": "FORTNIGHT",
        "monthly": "MONTH", "month": "MONTH", "annual": "YEAR", "year": "YEAR",
    }.get(str(row.get("rent_period") or "month").lower(), "MONTH")
    return {
        "source_site_id": source_site_id,
        "source_listing_id": str(row.get("source_listing_id") or ""),
        "source_url": row.get("source_url"),
        "current_status": "ACTIVE",
        "transaction_type": "RENT" if purpose == "RENT" else "SALE",
        "property_type_name": row.get("property_subtype") or row.get("property_class"),
        "province_name": row.get("province"), "city_name": row.get("city"),
        "suburb_name": row.get("suburb"), "local_area_name": row.get("local_area"),
        "street_name": row.get("street"), "location_name": row.get("local_area") or row.get("city"),
        "lot": row.get("allotment_number"), "section": row.get("section_number"),
        "portion": row.get("portion_number"), "bedrooms": row.get("bedrooms"),
        "bathrooms": row.get("bathrooms"), "land_area_sqm": row.get("land_area_m2"),
        "building_area_sqm": row.get("building_area_m2"), "price_amount": row.get("price"),
        "currency": "PGK", "price_type": "FIXED",
        "rental_period": period if purpose == "RENT" else None,
        "raw_payload": row.get("raw_fields") or {},
    }


class MarketPropertyLinkService:
    def __init__(self, database):
        self.db = database

    async def _candidate_address_ids(self, payload: Dict[str, Any]) -> List[str]:
        query: Dict[str, Any] = {"is_canonical": True, "valid_to": None}
        for id_key in ("province_id", "district_id", "city_id", "suburb_id", "local_area_id"):
            if payload.get(id_key):
                query[id_key] = payload[id_key]
        for name_key in ("province_name", "district_name", "city_name", "suburb_name", "local_area_name"):
            if payload.get(name_key):
                query[name_key] = {"$regex": f"^{re.escape(str(payload[name_key]).strip())}$", "$options": "i"}
        if len(query) == 2:
            return []
        docs = await self.db.property_addresses.find(
            query, {"_id": 0, "property_id": 1}
        ).limit(50).to_list(50)
        return list(dict.fromkeys(d["property_id"] for d in docs))

    async def _owner_filter(self, property_ids: List[str], owner_name: Optional[str]) -> List[str]:
        if not owner_name or not property_ids:
            return property_ids
        parties = await self.db.parties.find(
            {"normalized_name": norm(owner_name)}, {"_id": 0, "id": 1}
        ).to_list(20)
        party_ids = [p["id"] for p in parties]
        if not party_ids:
            return []
        links = await self.db.property_parties.find(
            {
                "property_id": {"$in": property_ids},
                "party_id": {"$in": party_ids},
                "relationship_type": {"$in": ["OWNER", "JOINT_OWNER"]},
            },
            {"_id": 0, "property_id": 1},
        ).to_list(50)
        return list(dict.fromkeys(link["property_id"] for link in links))

    async def match_master(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        direct = payload.get("trel_property_id")
        if direct and await self.db.master_properties.find_one({"id": direct}, {"_id": 0, "id": 1}):
            return {"status": "MATCHED", "master_property_id": direct, "confidence": 100, "rule": "DIRECT_TREL_ID", "candidates": [direct]}

        scheme, signature = parcel_signature(payload)
        address_ids = await self._candidate_address_ids(payload)
        if not scheme or not address_ids:
            return {"status": "UNMATCHED", "master_property_id": None, "confidence": 0, "rule": None, "candidates": []}
        query = {"property_id": {"$in": address_ids}, "identifier_scheme": scheme, **signature}
        if not signature.get("street_norm"):
            query.pop("street_norm", None)
        parcels = await self.db.property_parcels.find(
            query, {"_id": 0, "property_id": 1}
        ).limit(20).to_list(20)
        candidates = list(dict.fromkeys(p["property_id"] for p in parcels))
        candidates = await self._owner_filter(candidates, payload.get("owner_name"))
        if len(candidates) == 1:
            if payload.get("owner_name"):
                return {"status": "MATCHED", "master_property_id": candidates[0], "confidence": 100, "rule": scheme, "candidates": candidates}
            return {"status": "REVIEW_REQUIRED", "master_property_id": None, "confidence": 85, "rule": scheme, "candidates": candidates}
        if len(candidates) > 1:
            return {"status": "REVIEW_REQUIRED", "master_property_id": None, "confidence": 70, "rule": scheme, "candidates": candidates}
        return {"status": "UNMATCHED", "master_property_id": None, "confidence": 0, "rule": scheme, "candidates": []}

    async def ingest(self, payload: Dict[str, Any], actor_id: str) -> Dict[str, Any]:
        source = await self.db.source_sites.find_one({"id": payload["source_site_id"]}, {"_id": 0})
        if not source or not source.get("active", True):
            raise ValueError("Active source site not found")
        observed_at = payload.get("observed_at") or now_iso()
        existing = await self.db.source_listings.find_one({
            "source_site_id": payload["source_site_id"],
            "source_listing_id": payload["source_listing_id"],
        }, {"_id": 0})
        if not existing and payload.get("price_amount") is None:
            raise ValueError("A new market listing requires a usable numeric price")
        match = await self.match_master(payload)
        kind = origin_kind(source)
        listing_id = (existing or {}).get("id") or new_id()
        status = effective_status((existing or {}).get("current_status"), payload["current_status"])
        listing = {
            "id": listing_id,
            "source_site_id": payload["source_site_id"],
            "source_listing_id": payload["source_listing_id"],
            "source_url": payload["source_url"],
            "master_property_id": match["master_property_id"],
            "match_status": match["status"],
            "match_confidence": match["confidence"],
            "match_rule": match["rule"],
            "origin_kind": kind,
            "current_status": status,
            "transaction_type": payload["transaction_type"],
            "first_seen_at": (existing or {}).get("first_seen_at") or observed_at,
            "last_seen_at": (
                observed_at if payload["current_status"] not in {"NOT_SEEN", "REMOVED", "UNKNOWN"}
                else (existing or {}).get("last_seen_at") or observed_at
            ),
            "last_checked_at": observed_at,
            "created_at": (existing or {}).get("created_at") or now_iso(),
            "updated_at": now_iso(),
        }
        await self.db.source_listings.update_one(
            {"source_site_id": payload["source_site_id"], "source_listing_id": payload["source_listing_id"]},
            {"$set": listing}, upsert=True,
        )

        existing_observation = await self.db.source_listing_observations.find_one(
            {"source_listing_id": listing_id, "observed_at": observed_at},
            {"_id": 0, "id": 1},
        )
        observation_id = (existing_observation or {}).get("id") or new_id()
        monthly = (
            monthly_equivalent(payload["price_amount"], payload["transaction_type"], payload.get("rental_period"))
            if payload.get("price_amount") is not None else None
        )
        observation = {
            "id": observation_id,
            "source_listing_id": listing_id,
            "observed_at": observed_at,
            "status": status,
            "transaction_type": payload["transaction_type"],
            "property_type_id": payload.get("property_type_id"),
            "property_type_name": payload.get("property_type_name"),
            "province_id": payload.get("province_id"), "province_name": payload.get("province_name"),
            "district_id": payload.get("district_id"), "district_name": payload.get("district_name"),
            "city_id": payload.get("city_id"), "city_name": payload.get("city_name"),
            "suburb_id": payload.get("suburb_id"), "suburb_name": payload.get("suburb_name"),
            "local_area_id": payload.get("local_area_id"), "local_area_name": payload.get("local_area_name"),
            "street_name": payload.get("street_name"), "location_name": payload.get("location_name"),
            "lot": payload.get("lot"), "section": payload.get("section"), "portion": payload.get("portion"),
            "owner_name": payload.get("owner_name"),
            "bedrooms": payload.get("bedrooms"), "bathrooms": payload.get("bathrooms"),
            "land_area_sqm": payload.get("land_area_sqm"), "building_area_sqm": payload.get("building_area_sqm"),
            "priced_usable": payload.get("price_amount") is not None,
            "comparable_eligible": kind == "EXTERNAL",
            "raw_payload": payload.get("raw_payload") or {},
            "created_at": now_iso(),
        }
        await self.db.source_listing_observations.update_one(
            {"source_listing_id": listing_id, "observed_at": observed_at},
            {"$set": observation}, upsert=True,
        )
        if payload.get("price_amount") is not None:
            await self.db.observation_prices.update_one(
                {"observation_id": observation_id},
                {"$setOnInsert": {
                    "id": new_id(), "observation_id": observation_id,
                    "amount": float(payload["price_amount"]), "currency": "PGK",
                    "price_type": payload["price_type"], "rental_period": payload.get("rental_period"),
                    "monthly_equivalent": monthly, "created_at": now_iso(),
                }}, upsert=True,
            )
        if match["status"] == "REVIEW_REQUIRED":
            await self.db.property_match_reviews.update_one(
                {"source_listing_id": listing_id, "status": "OPEN"},
                {"$set": {"candidate_property_ids": match["candidates"], "updated_at": now_iso()},
                 "$setOnInsert": {"id": new_id(), "source_listing_id": listing_id, "status": "OPEN", "created_at": now_iso()}},
                upsert=True,
            )
        await self.db.audit_events.insert_one({
            "id": new_id(), "actor_id": actor_id, "action": "MARKET_OBSERVATION_INGESTED",
            "subject_type": "source_listing", "subject_id": listing_id,
            "payload": {"master_property_id": match["master_property_id"], "match_status": match["status"]},
            "created_at": now_iso(),
        })
        return {"source_listing": listing, "observation": observation, "match": match}

    async def list_evidence(self, limit: int = 100) -> List[Dict[str, Any]]:
        listings = await self.db.source_listings.find({}, {"_id": 0}).sort("last_seen_at", -1).limit(limit).to_list(limit)
        output = []
        for listing in listings:
            observation = await self.db.source_listing_observations.find_one(
                {"source_listing_id": listing["id"]}, {"_id": 0}, sort=[("observed_at", -1)]
            ) or {}
            observations = await self.db.source_listing_observations.find(
                {"source_listing_id": listing["id"]}, {"_id": 0, "id": 1}
            ).sort("observed_at", -1).limit(100).to_list(100)
            price = await self.db.observation_prices.find_one(
                {"observation_id": {"$in": [item["id"] for item in observations]}},
                {"_id": 0}, sort=[("created_at", -1)],
            ) or {}
            source = await self.db.source_sites.find_one({"id": listing["source_site_id"]}, {"_id": 0}) or {}
            output.append({
                **listing,
                "source_name": source.get("name"),
                "observed_at": observation.get("observed_at"),
                "property_type_name": observation.get("property_type_name"),
                "province_name": observation.get("province_name"),
                "city_name": observation.get("city_name"),
                "suburb_name": observation.get("suburb_name"),
                "local_area_name": observation.get("local_area_name"),
                "street_name": observation.get("street_name"),
                "lot": observation.get("lot"), "section": observation.get("section"), "portion": observation.get("portion"),
                "bedrooms": observation.get("bedrooms"), "bathrooms": observation.get("bathrooms"),
                "land_area_sqm": observation.get("land_area_sqm"), "building_area_sqm": observation.get("building_area_sqm"),
                "comparable_eligible": observation.get("comparable_eligible"),
                "raw_payload": observation.get("raw_payload") or {},
                "price_amount": price.get("amount"), "monthly_equivalent": price.get("monthly_equivalent"),
                "rental_period": price.get("rental_period"),
            })
        return output

    async def summary(self) -> Dict[str, int]:
        return {
            "active_listings": await self.db.source_listings.count_documents({"current_status": {"$in": ["ACTIVE", "RELISTED"]}}),
            "market_listings": await self.db.source_listings.count_documents({}),
            "matches_active": await self.db.source_listings.count_documents({"match_status": "MATCHED"}),
            "master_properties": await self.db.master_properties.count_documents({"lifecycle_status": {"$ne": "deleted"}}),
            "sources": await self.db.source_sites.count_documents({}),
            "active_sources": await self.db.source_sites.count_documents({"active": True}),
        }
