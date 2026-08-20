"""Feature-flagged property persistence for additive integrated-schema rollout.

Defaults preserve current behavior. Integrated reads and dual writes must be
enabled explicitly with environment variables.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from migrations.property_backfill import MIGRATION_VERSION, stable_id, transform

logger = logging.getLogger("trel.property_repository")

READ_LEGACY = "legacy"
READ_INTEGRATED = "integrated"
READ_COMPARE = "compare"


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


class PropertyRepository:
    def __init__(self, database):
        self.db = database

    @property
    def read_mode(self) -> str:
        value = os.getenv("TREL_PROPERTY_READ_MODE", READ_LEGACY).strip().lower()
        return value if value in {READ_LEGACY, READ_INTEGRATED, READ_COMPARE} else READ_LEGACY

    @property
    def dual_write(self) -> bool:
        return env_bool("TREL_PROPERTY_DUAL_WRITE")

    async def list(self, legacy_query: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
        legacy = await self.db.properties.find(
            legacy_query, {"_id": 0}
        ).sort("created_at", -1).to_list(limit)
        if self.read_mode == READ_LEGACY:
            return legacy
        integrated = await self._list_integrated(legacy_query, limit)
        if self.read_mode == READ_COMPARE:
            self._compare(legacy, integrated, "list")
            return legacy
        return integrated

    async def get(self, property_id: str) -> Optional[Dict[str, Any]]:
        legacy = await self.db.properties.find_one({"id": property_id}, {"_id": 0})
        if self.read_mode == READ_LEGACY:
            return legacy
        integrated = await self._get_integrated_by_legacy_id(property_id)
        if self.read_mode == READ_COMPARE:
            self._compare([legacy] if legacy else [], [integrated] if integrated else [], "get")
            return legacy
        return integrated

    async def create(self, document: Dict[str, Any]) -> Dict[str, Any]:
        await self.db.properties.insert_one(document)
        if self.dual_write:
            await self._mirror(document)
        document.pop("_id", None)
        return document

    async def update(self, property_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        await self.db.properties.update_one({"id": property_id}, {"$set": updates})
        result = await self.db.properties.find_one({"id": property_id}, {"_id": 0})
        if result and self.dual_write:
            await self._mirror(result)
        return result

    async def delete(self, property_id: str) -> None:
        await self.db.properties.delete_one({"id": property_id})
        if self.dual_write:
            await self.db.master_properties.update_one(
                {"legacy_property_id": property_id},
                {"$set": {"lifecycle_status": "deleted", "updated_at": datetime.now(timezone.utc).isoformat()}},
            )
            await self.db.listings.update_one(
                {"legacy_property_id": property_id},
                {"$set": {
                    "publication_status": "withdrawn",
                    "responsible_channel_active": False,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }},
            )

    async def _mirror(self, legacy_document: Dict[str, Any]) -> None:
        source_id = str(legacy_document.get("id") or "")
        try:
            target = transform(legacy_document, datetime.now(timezone.utc))
            for collection, document in target.items():
                await self.db[collection].update_one(
                    {"id": document["id"]}, {"$set": document}, upsert=True
                )
            now = datetime.now(timezone.utc)
            for target_type in ("master_property", "listing"):
                await self.db.migration_id_map.update_one(
                    {
                        "source_collection": "properties",
                        "source_id": source_id,
                        "target_type": target_type,
                    },
                    {"$set": {
                        "id": stable_id("map:" + target_type, source_id),
                        "source_collection": "properties",
                        "source_id": source_id,
                        "target_type": target_type,
                        "target_id": stable_id(target_type, source_id),
                        "migration_version": MIGRATION_VERSION,
                        "created_at": now,
                    }},
                    upsert=True,
                )
        except Exception as exc:
            logger.exception("Integrated property mirror failed for %s", source_id)
            try:
                now = datetime.now(timezone.utc)
                await self.db.migration_exceptions.update_one(
                    {"id": stable_id("dual-write-exception", source_id)},
                    {"$set": {
                        "id": stable_id("dual-write-exception", source_id),
                        "migration_version": MIGRATION_VERSION,
                        "source_collection": "properties",
                        "source_id": source_id,
                        "error_code": "DUAL_WRITE_FAILED",
                        "status": "OPEN",
                        "created_at": now,
                        "detail": type(exc).__name__,
                    }},
                    upsert=True,
                )
            except Exception:
                logger.exception("Could not record dual-write failure for %s", source_id)
            if env_bool("TREL_PROPERTY_DUAL_WRITE_STRICT"):
                raise

    async def _list_integrated(self, legacy_query: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
        query: Dict[str, Any] = {}
        mappings = {
            "listing_type": ("transaction_type", lambda value: str(value).upper()),
            "status": ("publication_status", str),
            "featured": ("featured", bool),
        }
        for legacy_field, (target_field, convert) in mappings.items():
            if legacy_field in legacy_query:
                query[target_field] = convert(legacy_query[legacy_field])
        if "price" in legacy_query:
            query["price_current"] = legacy_query["price"]
        if "$or" in legacy_query:
            term = next(iter(legacy_query["$or"][0].values())).get("$regex")
            query["$or"] = [
                {"title": {"$regex": term, "$options": "i"}},
                {"description": {"$regex": term, "$options": "i"}},
            ]

        listings = await self.db.listings.find(
            query, {"_id": 0}
        ).sort("created_at", -1).to_list(limit)
        output = []
        for listing in listings:
            item = await self._project_legacy_shape(listing)
            if not item:
                continue
            if "bedrooms" in legacy_query and item.get("bedrooms", 0) < legacy_query["bedrooms"].get("$gte", 0):
                continue
            if "property_type" in legacy_query and item.get("property_type") != legacy_query["property_type"]:
                continue
            if "location" in legacy_query and item.get("location") != legacy_query["location"]:
                continue
            output.append(item)
        return output[:limit]

    async def _get_integrated_by_legacy_id(self, legacy_id: str) -> Optional[Dict[str, Any]]:
        listing = await self.db.listings.find_one({"legacy_property_id": legacy_id}, {"_id": 0})
        return await self._project_legacy_shape(listing) if listing else None

    async def _project_legacy_shape(self, listing: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        property_id = listing.get("property_id")
        master = await self.db.master_properties.find_one({"id": property_id}, {"_id": 0})
        if not master:
            return None
        address = await self.db.property_addresses.find_one(
            {"property_id": property_id, "is_canonical": True, "valid_to": None}, {"_id": 0}
        ) or {}
        parcel = await self.db.property_parcels.find_one({"property_id": property_id}, {"_id": 0}) or {}
        attributes = await self.db.property_attributes.find_one({"property_id": property_id}, {"_id": 0}) or {}
        return {
            "id": listing.get("legacy_property_id") or property_id,
            "integrated_property_id": property_id,
            "integrated_listing_id": listing.get("id"),
            "title": listing.get("title") or master.get("title"),
            "listing_type": str(listing.get("transaction_type") or "").lower(),
            "property_type": master.get("property_type_name"),
            "price": listing.get("price_current"),
            "currency": listing.get("currency", "PGK"),
            "bedrooms": attributes.get("bedrooms", 0),
            "bathrooms": attributes.get("bathrooms", 0),
            "parking": attributes.get("parking", 0),
            "area_sqm": attributes.get("area_sqm"),
            "location": address.get("city_name"),
            "suburb": address.get("suburb_name"),
            "province": address.get("province_name"),
            "address": address.get("street_address"),
            "map_coords": address.get("map_coords"),
            "description": listing.get("description", ""),
            "features": attributes.get("features", []),
            "images": listing.get("images", []),
            "status": listing.get("publication_status"),
            "featured": bool(listing.get("featured")),
            "verified": master.get("verification_status") == "VERIFIED",
            "full_portion_number": parcel.get("portion"),
            "allotment_number": parcel.get("lot"),
            "section_number": parcel.get("section"),
            "total_area_ha": parcel.get("area_hectares"),
            "street_name": parcel.get("street_name"),
            "nearby_landmark": address.get("nearby_landmark"),
            "district": parcel.get("district_name"),
            "tenure_type": parcel.get("tenure_type"),
            "title_reference": parcel.get("title_reference"),
            "created_at": listing.get("created_at"),
            "updated_at": listing.get("updated_at"),
        }

    @staticmethod
    def _compare(legacy: List[Dict[str, Any]], integrated: List[Dict[str, Any]], operation: str) -> None:
        legacy_ids = {item.get("id") for item in legacy if item}
        integrated_ids = {item.get("id") for item in integrated if item}
        if legacy_ids != integrated_ids:
            logger.warning(
                "Property %s comparison mismatch: legacy=%s integrated=%s",
                operation, len(legacy_ids), len(integrated_ids),
            )
