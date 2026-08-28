"""Property persistence gateway for controlled integrated rollout.

Integrated is the final-system default. Set TREL_PROPERTY_STORAGE_MODE=legacy
only for an explicit rollback.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from core.db import client, now_iso
from core.integrated_property_service import IntegratedPropertyService

MODE_INTEGRATED = "integrated"
MODE_LEGACY = "legacy"


class PropertyRepository:
    def __init__(self, database):
        self.db = database
        self.integrated = IntegratedPropertyService(database, client)

    @property
    def storage_mode(self) -> str:
        value = os.getenv("TREL_PROPERTY_STORAGE_MODE", MODE_INTEGRATED).strip().lower()
        return value if value in {MODE_INTEGRATED, MODE_LEGACY} else MODE_LEGACY

    async def list(self, query: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
        if self.storage_mode == MODE_INTEGRATED:
            return await self.integrated.list(query, limit)
        legacy_query = dict(query)
        # Legacy properties collection stores `created_by` directly on the doc.
        return await self.db.properties.find(
            legacy_query, {"_id": 0}
        ).sort("created_at", -1).to_list(limit)

    async def get(self, property_id: str) -> Optional[Dict[str, Any]]:
        if self.storage_mode == MODE_INTEGRATED:
            return await self.integrated.get(property_id)
        return await self.db.properties.find_one({"id": property_id}, {"_id": 0})

    async def duplicate_check(
        self, payload: Dict[str, Any], exclude_property_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        if self.storage_mode == MODE_LEGACY:
            return []
        return await self.integrated.duplicate_check(payload, exclude_property_id)

    async def create(self, document: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
        if self.storage_mode == MODE_INTEGRATED:
            return await self.integrated.create(document, user)
        await self.db.properties.insert_one(document)
        document.pop("_id", None)
        return document

    async def update(
        self, property_id: str, document: Dict[str, Any], user: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        if self.storage_mode == MODE_INTEGRATED:
            return await self.integrated.update(property_id, document, user)
        document.pop("id", None)
        document.pop("_id", None)
        await self.db.properties.update_one({"id": property_id}, {"$set": document})
        return await self.db.properties.find_one({"id": property_id}, {"_id": 0})

    async def delete(self, property_id: str, user: Dict[str, Any]) -> bool:
        """Archive a property without destroying its record."""
        if self.storage_mode == MODE_INTEGRATED:
            return await self.integrated.delete(property_id, user)
        result = await self.db.properties.update_one(
            {"id": property_id},
            {"$set": {"status": "archived", "archived_at": now_iso(), "updated_at": now_iso()}},
        )
        return bool(result.matched_count)

    async def restore(self, property_id: str, user: Dict[str, Any]) -> bool:
        if self.storage_mode == MODE_INTEGRATED:
            return await self.integrated.restore(property_id, user)
        result = await self.db.properties.update_one(
            {"id": property_id, "status": "archived"},
            {"$set": {"status": "withdrawn", "updated_at": now_iso()},
             "$unset": {"archived_at": ""}},
        )
        return bool(result.matched_count)
