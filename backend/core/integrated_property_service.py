"""Transactional integrated Property graph service."""
from __future__ import annotations

import logging
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from pymongo.errors import OperationFailure

from core.db import detect_topology, new_id, now_iso, strict_transactions_required
from core.property_advertising_rules import duplicate_identity_match, identity_reasons

logger = logging.getLogger("trel")


class DuplicatePropertyError(Exception):
    def __init__(self, candidates: List[Dict[str, Any]]):
        super().__init__("Possible duplicate property")
        self.candidates = candidates


class PartialWriteError(Exception):
    """Raised when a non-transactional multi-collection write fails partway.

    Contains the original cause and the audit-log id created for the failure so
    callers can surface a clear message and operators can trace the orphan
    documents that were compensated (or, if compensation itself failed, are
    still present)."""

    def __init__(self, cause: Exception, failure_id: str):
        super().__init__(f"Partial write failure recorded as {failure_id}")
        self.cause = cause
        self.failure_id = failure_id


def norm(value: Any) -> Optional[str]:
    text = re.sub(r"\s+", " ", str(value or "").strip()).upper()
    return text or None


def feature_code(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", norm(value) or "").strip("_")


def identifier_scheme(payload: Dict[str, Any]) -> str:
    if payload.get("full_portion_number"):
        return "CUSTOMARY" if payload.get("tenure_type") == "CUSTOMARY" else "PORTION"
    return "URBAN_LOT_SECTION"


class _NoopTracker:
    """No-op tracker used when Mongo handles rollback for us."""

    async def track_insert(self, collection: str, document: Dict[str, Any]) -> None:
        return None

    async def compensate_and_record(self, exc: Exception) -> str:
        return ""


class _InsertTracker:
    """Records every insert issued during a non-transactional write.

    On failure, delete-many by id in reverse order and write a
    `partial_write_failures` audit document. If compensation itself fails we
    include that in the audit record so operators can trace orphans."""

    def __init__(self, db):
        self.db = db
        self.inserts: List[Tuple[str, str]] = []

    async def track_insert(self, collection: str, document: Dict[str, Any]) -> None:
        doc_id = document.get("id")
        if doc_id:
            self.inserts.append((collection, doc_id))

    async def compensate_and_record(self, exc: Exception) -> str:
        failure_id = new_id()
        rollback_status: List[Dict[str, Any]] = []
        for collection, doc_id in reversed(self.inserts):
            try:
                await self.db[collection].delete_one({"id": doc_id})
                rollback_status.append({"collection": collection, "id": doc_id, "status": "compensated"})
            except Exception as inner:
                rollback_status.append({
                    "collection": collection, "id": doc_id,
                    "status": "orphan", "error": str(inner)[:200],
                })
        await self.db.partial_write_failures.insert_one({
            "id": failure_id,
            "occurred_at": now_iso(),
            "error_message": str(exc)[:500],
            "error_type": type(exc).__name__,
            "attempted_inserts": [
                {"collection": c, "id": d} for c, d in self.inserts
            ],
            "rollback": rollback_status,
        })
        logger.error(
            "Non-transactional write failed (failure_id=%s): %s. Rollback: %s",
            failure_id, exc, rollback_status,
        )
        return failure_id


class IntegratedPropertyService:
    def __init__(self, database, client):
        self.db = database
        self.client = client
        self._topology: Optional[Dict[str, Any]] = None

    async def _detect_topology(self) -> Dict[str, Any]:
        if self._topology is None:
            self._topology = await detect_topology()
            logger.info(
                "IntegratedPropertyService topology=%s supports_transactions=%s strict=%s",
                self._topology.get("kind"),
                self._topology.get("supports_transactions"),
                strict_transactions_required(),
            )
            if not self._topology["supports_transactions"] and strict_transactions_required():
                # Fail loudly instead of silently degrading in production/Atlas.
                raise RuntimeError(
                    f"TREL_MONGO_STRICT_TRANSACTIONS is set (or Atlas URL detected) "
                    f"but MongoDB topology is {self._topology.get('kind')} which "
                    f"does not support multi-document transactions."
                )
        return self._topology

    @asynccontextmanager
    async def _txn(self):
        """Yield a session/tracker pair.

        - Replica-set/sharded → real transaction; on error, Mongo rolls back;
          `tracker.compensate()` is a no-op.
        - Standalone (dev/preview only, blocked by strict mode) → session is None
          and we track every insert; on error, delete them in reverse order.
        """
        topology = await self._detect_topology()
        if topology["supports_transactions"]:
            async with await self.client.start_session() as session:
                async with session.start_transaction():
                    yield session, _NoopTracker()
        else:
            tracker = _InsertTracker(self.db)
            try:
                yield None, tracker
            except (DuplicatePropertyError, ValueError):
                # Expected business errors — no partial write to compensate,
                # bubble up so routes/properties.py can map them cleanly.
                raise
            except Exception as exc:
                failure_id = await tracker.compensate_and_record(exc)
                raise PartialWriteError(exc, failure_id) from exc

    async def _resolve_reference(
        self,
        collection: str,
        supplied_id: Optional[str],
        name: Optional[str],
        session=None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        query: Dict[str, Any]
        if supplied_id:
            query = {"id": supplied_id}
        elif name:
            query = {"name": {"$regex": f"^{re.escape(str(name).strip())}$", "$options": "i"}}
            query.update(extra or {})
        else:
            raise ValueError(f"{collection} reference is required")
        result = await self.db[collection].find_one(query, {"_id": 0}, session=session)
        if not result:
            raise ValueError(f"Unknown {collection} reference")
        return result

    async def _resolve_or_create_optional(
        self,
        collection: str,
        supplied_id: Optional[str],
        name: Optional[str],
        parent: Dict[str, Any],
        session=None,
    ) -> Optional[Dict[str, Any]]:
        if not supplied_id and not str(name or "").strip():
            return None
        if supplied_id:
            existing = await self.db[collection].find_one(
                {"id": supplied_id}, {"_id": 0}, session=session
            )
            if not existing:
                raise ValueError(f"Unknown {collection} reference")
            return existing
        query = {"name": {"$regex": f"^{re.escape(str(name).strip())}$", "$options": "i"}, **parent}
        existing = await self.db[collection].find_one(query, {"_id": 0}, session=session)
        if existing:
            return existing
        document = {
            "id": new_id(),
            "name": str(name).strip(),
            **parent,
            "source": "property_form",
            "created_at": now_iso(),
        }
        await self.db[collection].insert_one(document, session=session)
        return document

    async def resolve_context(self, payload: Dict[str, Any], session=None) -> Dict[str, Any]:
        province_name = payload.get("province")
        if norm(province_name) in {"NCD", "NATIONAL CAPITAL DISTRICT"}:
            province_name = "National Capital District"
        province = await self._resolve_reference(
            "provinces", payload.get("province_id"), province_name, session
        )
        city = await self._resolve_or_create_optional(
            "cities", payload.get("city_id"), payload.get("location"),
            {"province_id": province["id"]}, session,
        )
        if not city:
            raise ValueError("City or town reference is required")
        suburb = await self._resolve_or_create_optional(
            "suburbs", payload.get("suburb_id"), payload.get("suburb") or payload.get("location"),
            {"city_id": city["id"]}, session,
        )
        if not suburb:
            raise ValueError("Suburb or town reference is required")
        type_aliases = {
            "APARTMENT / UNIT": "Apartment", "TOWNHOUSE": "Town House",
            "OFFICE SPACE": "Commercial", "RETAIL": "Commercial",
            "COMMERCIAL BUILDING": "Commercial", "HOTEL / LODGE": "Commercial",
            "WAREHOUSE": "Commercial", "FACTORY": "Commercial", "WORKSHOP": "Commercial",
            "LAND": "Vacant Land – Urban Subdivided", "RESIDENTIAL LAND": "Vacant Land – Urban Subdivided",
            "COMMERCIAL LAND": "Vacant Land – Urban Subdivided", "INDUSTRIAL LAND": "Vacant Land – Urban Subdivided",
            "FARM": "Large Land – Portion / Customary", "PLANTATION": "Large Land – Portion / Customary",
            "RURAL LAND": "Large Land – Portion / Customary",
        }
        property_type_name = type_aliases.get(norm(payload.get("property_type")), payload.get("property_type"))
        try:
            property_type = await self._resolve_reference(
                "property_types", payload.get("property_type_id"), property_type_name, session,
                {"is_active": True},
            )
        except ValueError:
            if norm(property_type_name) != "OTHER" or payload.get("property_type_id"):
                raise
            await self.db.property_types.update_one(
                {"name": "Other"},
                {"$setOnInsert": {"id": new_id(), "name": "Other", "is_active": True,
                                  "legal_scheme": "portion" if identifier_scheme(payload) in {"PORTION", "CUSTOMARY"} else "lot_section_street",
                                  "order": 999, "created_at": now_iso()}},
                upsert=True, session=session,
            )
            property_type = await self._resolve_reference(
                "property_types", None, "Other", session, {"is_active": True},
            )
        district = None
        if payload.get("district_id") or payload.get("district"):
            district = await self._resolve_or_create_optional(
                "districts", payload.get("district_id"), payload.get("district"),
                {"province_id": province["id"]}, session,
            )
        local_area = None
        if payload.get("local_area_id") or payload.get("local_area"):
            local_area = await self._resolve_or_create_optional(
                "local_areas", payload.get("local_area_id"), payload.get("local_area"),
                {"suburb_id": suburb["id"]}, session,
            )
        return {
            "province": province,
            "city": city,
            "suburb": suburb,
            "property_type": property_type,
            "district": district,
            "local_area": local_area,
        }

    async def duplicate_check(
        self,
        payload: Dict[str, Any],
        exclude_property_id: Optional[str] = None,
        session=None,
    ) -> List[Dict[str, Any]]:
        query = {"property_id": {"$ne": exclude_property_id}} if exclude_property_id else {}
        parcels = await self.db.property_parcels.find(
            query, {"_id": 0}, session=session
        ).limit(5000).to_list(5000)
        output = []
        for parcel in parcels:
            property_id = parcel["property_id"]
            address = await self.db.property_addresses.find_one(
                {"property_id": property_id, "valid_to": None}, {"_id": 0}, session=session
            ) or await self.db.property_addresses.find_one(
                {"property_id": property_id}, {"_id": 0}, session=session
            ) or {}
            candidate = {
                "identity_scheme": "LARGE_PORTION" if parcel.get("identifier_scheme") in {"PORTION", "CUSTOMARY"} else "SERVICED",
                "portion": parcel.get("portion"),
                "location": parcel.get("location_norm") or address.get("district_name"),
                "city": address.get("city_name"),
                "lot": parcel.get("lot"),
                "section": parcel.get("section"),
                "street": address.get("street_name") or parcel.get("street_norm"),
                "suburb": address.get("suburb_name"),
            }
            if not duplicate_identity_match(payload, candidate):
                continue
            master = await self.db.master_properties.find_one(
                {"id": property_id}, {"_id": 0, "id": 1, "title": 1}, session=session
            )
            output.append({
                "property_id": property_id,
                "title": (master or {}).get("title") or "Existing property",
                "confidence": 100,
                "reasons": identity_reasons(payload),
            })
        return output

    async def _party(self, payload: Dict[str, Any], session, tracker=None) -> Dict[str, Any]:
        owner_name = str(payload.get("owner_name") or "").strip()
        if not owner_name:
            raise ValueError("Owner name is required")
        owner_norm = norm(owner_name)
        contact_queries = []
        if payload.get("owner_email"):
            contact_queries.append({"email_norm": norm(payload["owner_email"])})
        if payload.get("owner_phone"):
            contact_queries.append({"phone_norm": norm(payload["owner_phone"])})
        query: Dict[str, Any] = {"normalized_name": owner_norm}
        if contact_queries:
            query["$or"] = contact_queries
        existing = await self.db.parties.find_one(query, {"_id": 0}, session=session)
        if existing:
            return existing
        party = {
            "id": new_id(),
            "party_type": "PERSON",
            "display_name": owner_name,
            "normalized_name": owner_norm,
            "email": payload.get("owner_email"),
            "email_norm": norm(payload.get("owner_email")),
            "phone": payload.get("owner_phone"),
            "phone_norm": norm(payload.get("owner_phone")),
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        await self.db.parties.insert_one(party, session=session)
        if tracker is not None:
            await tracker.track_insert("parties", party)
        return party

    def build_graph(
        self,
        payload: Dict[str, Any],
        user: Dict[str, Any],
        context: Dict[str, Any],
        party: Dict[str, Any],
        property_id: Optional[str] = None,
        listing_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        property_id = property_id or new_id()
        listing_id = listing_id or new_id()
        timestamp = now_iso()
        scheme = identifier_scheme(payload)
        status = payload.get("status") or "draft"
        transaction_type = str(payload["listing_type"]).upper()
        master = {
            "id": property_id,
            "property_type_id": context["property_type"]["id"],
            "property_type_name": context["property_type"]["name"],
            "title": str(payload["title"]).strip(),
            "lifecycle_status": status,
            "verification_status": "VERIFIED" if payload.get("verified") else "UNVERIFIED",
            "created_by": user["id"],
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        address = {
            "id": new_id(),
            "property_id": property_id,
            "province_id": context["province"]["id"],
            "city_id": context["city"]["id"],
            "suburb_id": context["suburb"]["id"],
            "district_id": context["district"]["id"] if context.get("district") else None,
            "district_name": context["district"]["name"] if context.get("district") else None,
            "local_area_id": context["local_area"]["id"] if context.get("local_area") else None,
            "local_area_name": context["local_area"]["name"] if context.get("local_area") else None,
            "province_name": context["province"]["name"],
            "city_name": context["city"]["name"],
            "suburb_name": context["suburb"]["name"],
            "street_id": payload.get("street_id"),
            "street_name": payload.get("street_name"),
            "street_address": payload.get("address"),
            "nearby_landmark": payload.get("nearby_landmark"),
            "map_coords": payload.get("map_coords"),
            "is_canonical": True,
            "valid_to": None,
            "created_at": timestamp,
        }
        parcel = {
            "id": new_id(),
            "property_id": property_id,
            "identifier_scheme": scheme,
            "province_id": context["province"]["id"],
            "district_id": context["district"]["id"] if context.get("district") else None,
            "city_id": context["city"]["id"],
            "suburb_id": context["suburb"]["id"],
            "street_id": payload.get("street_id"),
            "street_norm": norm(payload.get("street_name")),
            "section": payload.get("section_number"),
            "section_norm": norm(payload.get("section_number")),
            "lot": payload.get("allotment_number"),
            "lot_norm": norm(payload.get("allotment_number")),
            "location_norm": norm(payload.get("location")),
            "portion": payload.get("full_portion_number"),
            "portion_norm": norm(payload.get("full_portion_number")),
            "title_reference": payload.get("title_reference"),
            "tenure_type": payload.get("tenure_type") or None,
            "area_hectares": payload.get("total_area_ha"),
            "created_at": timestamp,
        }
        attributes = {
            "id": new_id(),
            "property_id": property_id,
            "bedrooms": int(payload.get("bedrooms") or 0),
            "bathrooms": int(payload.get("bathrooms") or 0),
            "parking": int(payload.get("parking") or 0),
            "area_sqm": payload.get("area_sqm"),
            "building_area_ha": payload.get("building_area_ha"),
            "furnished": payload.get("furnished"),
            "condition": payload.get("condition"),
            "year_built": payload.get("year_built"),
            "special_features": payload.get("special_features"),
            "features": list(payload.get("features") or []),
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        authority_basis = payload.get("owner_relationship") or "OWNER"
        property_party = {
            "id": new_id(),
            "property_id": property_id,
            "party_id": party["id"],
            # owner_name identifies the legal owner used by the duplicate rule.
            # Agent/representative capacity belongs to advertiser_authorities.
            "relationship_type": authority_basis if authority_basis in {"OWNER", "JOINT_OWNER"} else "OWNER",
            "authority_status": payload.get("authority_status") or "PENDING",
            "created_at": timestamp,
        }
        listing = {
            "id": listing_id,
            "property_id": property_id,
            "transaction_type": transaction_type,
            "publication_status": status,
            "responsible_channel_active": status in {"active", "under_offer"},
            "price_current": float(payload["price"]),
            "currency": payload.get("currency") or "PGK",
            "title": str(payload["title"]).strip(),
            "description": payload.get("description") or "",
            "featured": bool(payload.get("featured")),
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        price = {
            "id": new_id(),
            "listing_id": listing_id,
            "amount": float(payload["price"]),
            "currency": payload.get("currency") or "PGK",
            "basis": "TOTAL_SALE" if transaction_type == "SALE" else "MONTHLY_RENT",
            "effective_from": timestamp,
            "created_at": timestamp,
        }
        history = {
            "id": new_id(),
            "listing_id": listing_id,
            "status": status,
            "changed_at": timestamp,
            "changed_by": user["id"],
        }
        return {
            "master_properties": master,
            "property_addresses": address,
            "property_parcels": parcel,
            "property_attributes": attributes,
            "property_parties": property_party,
            "listings": listing,
            "listing_prices": price,
            "listing_status_history": history,
        }

    async def create(self, payload: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
        async with self._txn() as (session, tracker):
            context = await self.resolve_context(payload, session)
            candidates = await self.duplicate_check(payload, session=session)
            if candidates and not payload.get("duplicate_override"):
                raise DuplicatePropertyError(candidates)
            party = await self._party(payload, session, tracker)
            graph = self.build_graph(payload, user, context, party)
            for collection, document in graph.items():
                await self.db[collection].insert_one(document, session=session)
                await tracker.track_insert(collection, document)
            await self._replace_media_features_documents(
                graph["master_properties"]["id"], graph["listings"]["id"], payload, session, tracker
            )
            authority = {
                "id": new_id(),
                "property_id": graph["master_properties"]["id"],
                "owner_party_id": party["id"],
                "submitted_by_user_id": user["id"],
                "authority_basis": payload.get("owner_relationship") or "OWNER",
                "status": payload.get("authority_status") or "PENDING",
                "created_at": now_iso(),
            }
            await self.db.advertiser_authorities.insert_one(authority, session=session)
            await tracker.track_insert("advertiser_authorities", authority)
            audit = {
                "id": new_id(), "action": "PROPERTY_CREATED",
                "subject_type": "master_property",
                "subject_id": graph["master_properties"]["id"],
                "actor_id": user["id"], "created_at": now_iso(),
            }
            await self.db.audit_events.insert_one(audit, session=session)
            await tracker.track_insert("audit_events", audit)
            return await self._project(graph["listings"], session)

    async def update(self, property_id: str, payload: Dict[str, Any], user: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        async with self._txn() as (session, tracker):
            master = await self.db.master_properties.find_one(
                {"id": property_id}, {"_id": 0}, session=session
            )
            if not master:
                return None
            listing = await self.db.listings.find_one(
                {"property_id": property_id, "responsible_channel_active": True},
                {"_id": 0}, session=session
            ) or await self.db.listings.find_one(
                {"property_id": property_id}, {"_id": 0}, session=session
            )
            context = await self.resolve_context(payload, session)
            candidates = await self.duplicate_check(payload, property_id, session)
            if candidates and not payload.get("duplicate_override"):
                raise DuplicatePropertyError(candidates)
            party = await self._party(payload, session, tracker)
            graph = self.build_graph(
                payload, user, context, party, property_id,
                listing["id"] if listing else None,
            )
            immutable = {"created_at": master.get("created_at") or now_iso()}
            graph["master_properties"].update(immutable)
            for collection in (
                "master_properties", "property_addresses", "property_parcels",
                "property_attributes", "property_parties", "listings",
            ):
                document = graph[collection]
                key = {"id": document["id"]} if collection in {"master_properties", "listings"} else {"property_id": property_id}
                await self.db[collection].update_one(
                    key, {"$set": document}, upsert=True, session=session
                )
            current_price = listing.get("price_current") if listing else None
            if current_price != float(payload["price"]):
                await self.db.listing_prices.insert_one(graph["listing_prices"], session=session)
                await tracker.track_insert("listing_prices", graph["listing_prices"])
            if not listing or listing.get("publication_status") != graph["listings"]["publication_status"]:
                await self.db.listing_status_history.insert_one(
                    graph["listing_status_history"], session=session
                )
                await tracker.track_insert("listing_status_history", graph["listing_status_history"])
            await self._replace_media_features_documents(
                property_id, graph["listings"]["id"], payload, session, tracker
            )
            await self.db.advertiser_authorities.update_one(
                {"property_id": property_id},
                {"$set": {
                    "owner_party_id": party["id"],
                    "submitted_by_user_id": user["id"],
                    "authority_basis": payload.get("owner_relationship") or "OWNER",
                    "status": payload.get("authority_status") or "PENDING",
                    "updated_at": now_iso(),
                }, "$setOnInsert": {"id": new_id(), "created_at": now_iso()}},
                upsert=True,
                session=session,
            )
            await self.db.audit_events.insert_one({
                "id": new_id(), "action": "PROPERTY_UPDATED",
                "subject_type": "master_property", "subject_id": property_id,
                "actor_id": user["id"], "created_at": now_iso(),
            }, session=session)
            return await self._project(graph["listings"], session)

    async def _replace_media_features_documents(self, property_id, listing_id, payload, session, tracker=None) -> None:
        await self.db.listing_media.delete_many({"listing_id": listing_id}, session=session)
        media = [{
            "id": new_id(), "listing_id": listing_id, "url": url,
            "sort_order": index, "is_cover": index == 0, "created_at": now_iso(),
        } for index, url in enumerate(payload.get("images") or []) if url]
        if media:
            await self.db.listing_media.insert_many(media, session=session)
            if tracker is not None:
                for m in media:
                    await tracker.track_insert("listing_media", m)

        await self.db.listing_features.delete_many({"listing_id": listing_id}, session=session)
        links = []
        for name in payload.get("features") or []:
            code = feature_code(name)
            if not code:
                continue
            feature = await self.db.features.find_one({"code": code}, {"_id": 0}, session=session)
            if not feature:
                feature = {"id": new_id(), "code": code, "name": str(name).strip(), "created_at": now_iso()}
                await self.db.features.insert_one(feature, session=session)
                if tracker is not None:
                    await tracker.track_insert("features", feature)
            links.append({
                "id": new_id(), "listing_id": listing_id,
                "feature_id": feature["id"], "created_at": now_iso(),
            })
        if links:
            await self.db.listing_features.insert_many(links, session=session)
            if tracker is not None:
                for l in links:
                    await tracker.track_insert("listing_features", l)

        documents = payload.get("documents") or []
        await self.db.property_documents.delete_many({"property_id": property_id}, session=session)
        if documents:
            doc_rows = [{
                "id": new_id(), "property_id": property_id,
                "document_type": item["document_type"], "url": item["url"],
                "status": item.get("status") or "UPLOADED", "created_at": now_iso(),
            } for item in documents]
            await self.db.property_documents.insert_many(doc_rows, session=session)
            if tracker is not None:
                for d in doc_rows:
                    await tracker.track_insert("property_documents", d)

    async def list(self, query: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
        listing_query: Dict[str, Any] = {}
        if query.get("listing_type"):
            listing_query["transaction_type"] = str(query["listing_type"]).upper()
        if query.get("status"):
            listing_query["publication_status"] = query["status"]
        if "featured" in query:
            listing_query["featured"] = query["featured"]
        if query.get("price"):
            listing_query["price_current"] = query["price"]
        if query.get("$or"):
            term = next(iter(query["$or"][0].values())).get("$regex")
            listing_query["$or"] = [
                {"title": {"$regex": term, "$options": "i"}},
                {"description": {"$regex": term, "$options": "i"}},
            ]
        # Ownership scoping: `created_by` is stored on `master_properties`, so
        # pre-filter to the caller's own property_ids before pulling listings.
        if query.get("created_by"):
            own_property_ids = await self.db.master_properties.distinct(
                "id", {"created_by": query["created_by"]}
            )
            listing_query["property_id"] = {"$in": own_property_ids}
        listings = await self.db.listings.find(
            listing_query, {"_id": 0}
        ).sort("created_at", -1).to_list(limit * 2)
        output = []
        for listing in listings:
            result = await self._project(listing)
            if not result:
                continue
            if query.get("property_type") and result.get("property_type") != query["property_type"]:
                continue
            if query.get("location") and result.get("location") != query["location"]:
                continue
            if query.get("bedrooms") and result.get("bedrooms", 0) < query["bedrooms"].get("$gte", 0):
                continue
            output.append(result)
        return output[:limit]

    async def get(self, property_id: str) -> Optional[Dict[str, Any]]:
        listing = await self.db.listings.find_one(
            {"$or": [{"id": property_id}, {"property_id": property_id}]}, {"_id": 0}
        )
        return await self._project(listing) if listing else None

    async def delete(self, property_id: str, user: Dict[str, Any]) -> bool:
        timestamp = now_iso()
        master_result = await self.db.master_properties.update_one(
            {"id": property_id},
            {"$set": {"lifecycle_status": "archived", "archived_at": timestamp, "updated_at": timestamp}},
        )
        await self.db.listings.update_many(
            {"property_id": property_id},
            {"$set": {
                "publication_status": "withdrawn",
                "responsible_channel_active": False,
                "updated_at": timestamp,
            }},
        )
        if master_result.matched_count:
            await self.db.audit_events.insert_one({
                "id": new_id(), "action": "PROPERTY_ARCHIVED",
                "subject_type": "master_property", "subject_id": property_id,
                "actor_id": user["id"], "created_at": timestamp,
            })
            return True
        return False

    async def restore(self, property_id: str, user: Dict[str, Any]) -> bool:
        timestamp = now_iso()
        result = await self.db.master_properties.update_one(
            {"id": property_id, "lifecycle_status": "archived"},
            {"$set": {"lifecycle_status": "active", "updated_at": timestamp},
             "$unset": {"archived_at": ""}},
        )
        if result.matched_count:
            await self.db.audit_events.insert_one({
                "id": new_id(), "action": "PROPERTY_RESTORED",
                "subject_type": "master_property", "subject_id": property_id,
                "actor_id": user["id"], "created_at": timestamp,
            })
            return True
        return False

    async def _project(self, listing: Dict[str, Any], session=None) -> Optional[Dict[str, Any]]:
        if not listing:
            return None
        property_id = listing["property_id"]
        master = await self.db.master_properties.find_one({"id": property_id}, {"_id": 0}, session=session)
        if not master:
            return None
        address = await self.db.property_addresses.find_one(
            {"property_id": property_id, "is_canonical": True, "valid_to": None},
            {"_id": 0}, session=session
        ) or {}
        parcel = await self.db.property_parcels.find_one({"property_id": property_id}, {"_id": 0}, session=session) or {}
        attributes = await self.db.property_attributes.find_one({"property_id": property_id}, {"_id": 0}, session=session) or {}
        owner_link = await self.db.property_parties.find_one(
            {"property_id": property_id, "relationship_type": {"$in": ["OWNER", "JOINT_OWNER"]}},
            {"_id": 0}, session=session
        ) or await self.db.property_parties.find_one({"property_id": property_id}, {"_id": 0}, session=session)
        owner = await self.db.parties.find_one({"id": (owner_link or {}).get("party_id")}, {"_id": 0}, session=session) if owner_link else {}
        authority = await self.db.advertiser_authorities.find_one(
            {"property_id": property_id}, {"_id": 0}, session=session
        ) or {}
        # Compute "owner verified" flag — the property was submitted by a
        # Property Advertiser whose profile AND at least one government ID are
        # both VERIFIED. Used to display the "Verified Owner" badge on the
        # public property card.
        owner_verified = False
        submitter_id = authority.get("submitted_by_user_id") or master.get("created_by")
        if submitter_id:
            profile_verified = await self.db.advertiser_profiles.find_one(
                {"user_id": submitter_id, "status": "VERIFIED"},
                {"_id": 0, "id": 1}, session=session,
            )
            id_verified = await self.db.identity_documents.find_one(
                {"user_id": submitter_id, "status": "VERIFIED"},
                {"_id": 0, "id": 1}, session=session,
            )
            owner_verified = bool(profile_verified and id_verified)
        media = await self.db.listing_media.find(
            {"listing_id": listing["id"]}, {"_id": 0}
        ).sort("sort_order", 1).to_list(100)
        documents = await self.db.property_documents.find(
            {"property_id": property_id}, {"_id": 0}
        ).sort("created_at", 1).to_list(100)
        return {
            "id": property_id,
            "integrated_property_id": property_id,
            "integrated_listing_id": listing["id"],
            "title": listing.get("title") or master.get("title"),
            "listing_type": str(listing.get("transaction_type") or "").lower(),
            "property_type": master.get("property_type_name"),
            "property_type_id": master.get("property_type_id"),
            "price": listing.get("price_current"),
            "currency": listing.get("currency", "PGK"),
            "price_type": listing.get("price_type") or "PGK",
            "price_label": listing.get("price_label"),
            "listing_reference": listing.get("listing_reference"),
            "service": listing.get("service"),
            "bedrooms": attributes.get("bedrooms", 0),
            "bathrooms": attributes.get("bathrooms", 0),
            "parking": attributes.get("parking", 0),
            "area_sqm": attributes.get("area_sqm"),
            "building_area_ha": attributes.get("building_area_ha"),
            "furnished": attributes.get("furnished"),
            "condition": attributes.get("condition"),
            "year_built": attributes.get("year_built"),
            "special_features": attributes.get("special_features"),
            "location": address.get("city_name"),
            "city_id": address.get("city_id"),
            "suburb": address.get("suburb_name"),
            "suburb_id": address.get("suburb_id"),
            "province": address.get("province_name"),
            "province_id": address.get("province_id"),
            "address": address.get("street_address"),
            "map_coords": address.get("map_coords"),
            "description": listing.get("description", ""),
            "features": attributes.get("features", []),
            "images": [item["url"] for item in media],
            "documents": documents,
            "status": "archived" if master.get("lifecycle_status") == "archived" else listing.get("publication_status"),
            "archived": master.get("lifecycle_status") == "archived",
            "featured": bool(listing.get("featured")),
            "verified": master.get("verification_status") == "VERIFIED",
            "full_portion_number": parcel.get("portion"),
            "allotment_number": parcel.get("lot"),
            "section_number": parcel.get("section"),
            "total_area_ha": parcel.get("area_hectares"),
            "street_name": address.get("street_name"),
            "nearby_landmark": address.get("nearby_landmark"),
            "district_id": address.get("district_id"),
            "district": address.get("district_name"),
            "local_area_id": address.get("local_area_id"),
            "local_area": address.get("local_area_name"),
            "tenure_type": parcel.get("tenure_type"),
            "title_reference": parcel.get("title_reference"),
            "owner_name": (owner or {}).get("display_name"),
            "owner_email": (owner or {}).get("email"),
            "owner_phone": (owner or {}).get("phone"),
            "owner_relationship": authority.get("authority_basis") or (owner_link or {}).get("relationship_type"),
            "authority_status": authority.get("status") or (owner_link or {}).get("authority_status"),
            "owner_verified": owner_verified,
            "created_at": listing.get("created_at"),
            "updated_at": listing.get("updated_at"),
        }
