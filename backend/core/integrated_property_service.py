"""Transactional integrated Property graph service."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from core.db import new_id, now_iso


class DuplicatePropertyError(Exception):
    def __init__(self, candidates: List[Dict[str, Any]]):
        super().__init__("Possible duplicate property")
        self.candidates = candidates


def norm(value: Any) -> Optional[str]:
    text = re.sub(r"\s+", " ", str(value or "").strip()).upper()
    return text or None


def feature_code(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", norm(value) or "").strip("_")


def identifier_scheme(payload: Dict[str, Any]) -> str:
    if payload.get("full_portion_number"):
        return "CUSTOMARY" if payload.get("tenure_type") == "CUSTOMARY" else "PORTION"
    return "URBAN_LOT_SECTION"


class IntegratedPropertyService:
    def __init__(self, database, client):
        self.db = database
        self.client = client

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
        province = await self._resolve_reference(
            "provinces", payload.get("province_id"), payload.get("province"), session
        )
        city = await self._resolve_reference(
            "cities", payload.get("city_id"), payload.get("location"), session,
            {"province_id": province["id"]},
        )
        suburb = await self._resolve_reference(
            "suburbs", payload.get("suburb_id"), payload.get("suburb"), session,
            {"city_id": city["id"]},
        )
        property_type = await self._resolve_reference(
            "property_types", payload.get("property_type_id"), payload.get("property_type"), session,
            {"is_active": True},
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

    def _parcel_filter(self, payload: Dict[str, Any], context: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
        scheme = identifier_scheme(payload)
        if scheme == "URBAN_LOT_SECTION":
            query = {
                "identifier_scheme": scheme,
                "province_id": context["province"]["id"],
                "suburb_id": context["suburb"]["id"],
                "street_norm": norm(payload.get("street_name")),
                "section_norm": norm(payload.get("section_number")),
                "lot_norm": norm(payload.get("allotment_number")),
            }
            reasons = ["same province", "same suburb", "same street", "same section", "same lot"]
        else:
            query = {
                "identifier_scheme": {"$in": ["PORTION", "CUSTOMARY"]},
                "province_id": context["province"]["id"],
                "district_id": context["district"]["id"] if context.get("district") else None,
                "location_norm": norm(payload.get("location")),
                "portion_norm": norm(payload.get("full_portion_number")),
            }
            reasons = ["same province", "same district", "same location", "same portion"]
        return query, reasons

    async def duplicate_check(
        self,
        payload: Dict[str, Any],
        exclude_property_id: Optional[str] = None,
        session=None,
    ) -> List[Dict[str, Any]]:
        context = await self.resolve_context(payload, session)
        query, reasons = self._parcel_filter(payload, context)
        if exclude_property_id:
            query["property_id"] = {"$ne": exclude_property_id}
        parcels = await self.db.property_parcels.find(
            query, {"_id": 0, "property_id": 1}, session=session
        ).limit(10).to_list(10)
        output = []
        owner_norm = norm(payload.get("owner_name"))
        for parcel in parcels:
            property_id = parcel["property_id"]
            master = await self.db.master_properties.find_one(
                {"id": property_id}, {"_id": 0, "id": 1, "title": 1}, session=session
            )
            owner_match = False
            if owner_norm:
                links = self.db.property_parties.find(
                    {"property_id": property_id, "relationship_type": {"$in": ["OWNER", "JOINT_OWNER"]}},
                    {"_id": 0, "party_id": 1},
                    session=session,
                )
                async for link in links:
                    party = await self.db.parties.find_one(
                        {"id": link["party_id"], "normalized_name": owner_norm},
                        {"_id": 0, "id": 1},
                        session=session,
                    )
                    if party:
                        owner_match = True
                        break
            matched_reasons = list(reasons)
            if owner_match:
                matched_reasons.append("same owner")
            output.append({
                "property_id": property_id,
                "title": (master or {}).get("title") or "Existing property",
                "confidence": 100 if owner_match else 90,
                "reasons": matched_reasons,
            })
        return output

    async def _party(self, payload: Dict[str, Any], session) -> Dict[str, Any]:
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
            "features": list(payload.get("features") or []),
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        property_party = {
            "id": new_id(),
            "property_id": property_id,
            "party_id": party["id"],
            "relationship_type": payload.get("owner_relationship") or "OWNER",
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
        async with await self.client.start_session() as session:
            async with session.start_transaction():
                context = await self.resolve_context(payload, session)
                candidates = await self.duplicate_check(payload, session=session)
                if candidates and not payload.get("duplicate_override"):
                    raise DuplicatePropertyError(candidates)
                party = await self._party(payload, session)
                graph = self.build_graph(payload, user, context, party)
                for collection, document in graph.items():
                    await self.db[collection].insert_one(document, session=session)
                await self._replace_media_features_documents(
                    graph["master_properties"]["id"], graph["listings"]["id"], payload, session
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
                await self.db.audit_events.insert_one({
                    "id": new_id(), "action": "PROPERTY_CREATED",
                    "subject_type": "master_property",
                    "subject_id": graph["master_properties"]["id"],
                    "actor_id": user["id"], "created_at": now_iso(),
                }, session=session)
                return await self._project(graph["listings"], session)

    async def update(self, property_id: str, payload: Dict[str, Any], user: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        async with await self.client.start_session() as session:
            async with session.start_transaction():
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
                party = await self._party(payload, session)
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
                if not listing or listing.get("publication_status") != graph["listings"]["publication_status"]:
                    await self.db.listing_status_history.insert_one(
                        graph["listing_status_history"], session=session
                    )
                await self._replace_media_features_documents(
                    property_id, graph["listings"]["id"], payload, session
                )
                await self.db.audit_events.insert_one({
                    "id": new_id(), "action": "PROPERTY_UPDATED",
                    "subject_type": "master_property", "subject_id": property_id,
                    "actor_id": user["id"], "created_at": now_iso(),
                }, session=session)
                return await self._project(graph["listings"], session)

    async def _replace_media_features_documents(self, property_id, listing_id, payload, session) -> None:
        await self.db.listing_media.delete_many({"listing_id": listing_id}, session=session)
        media = [{
            "id": new_id(), "listing_id": listing_id, "url": url,
            "sort_order": index, "is_cover": index == 0, "created_at": now_iso(),
        } for index, url in enumerate(payload.get("images") or []) if url]
        if media:
            await self.db.listing_media.insert_many(media, session=session)

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
            links.append({
                "id": new_id(), "listing_id": listing_id,
                "feature_id": feature["id"], "created_at": now_iso(),
            })
        if links:
            await self.db.listing_features.insert_many(links, session=session)

        documents = payload.get("documents") or []
        if documents:
            await self.db.property_documents.delete_many({"property_id": property_id}, session=session)
            await self.db.property_documents.insert_many([{
                "id": new_id(), "property_id": property_id,
                "document_type": item["document_type"], "url": item["url"],
                "status": item.get("status") or "UPLOADED", "created_at": now_iso(),
            } for item in documents], session=session)

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
            {"$set": {"lifecycle_status": "deleted", "updated_at": timestamp}},
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
                "id": new_id(), "action": "PROPERTY_WITHDRAWN",
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
            "bedrooms": attributes.get("bedrooms", 0),
            "bathrooms": attributes.get("bathrooms", 0),
            "parking": attributes.get("parking", 0),
            "area_sqm": attributes.get("area_sqm"),
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
            "status": listing.get("publication_status"),
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
            "owner_relationship": (owner_link or {}).get("relationship_type"),
            "authority_status": (owner_link or {}).get("authority_status"),
            "created_at": listing.get("created_at"),
            "updated_at": listing.get("updated_at"),
        }
