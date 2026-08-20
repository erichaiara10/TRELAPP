import asyncio
import re

from core.market_property_link import (
    MarketPropertyLinkService,
    effective_status,
    monthly_equivalent,
    origin_kind,
    parcel_signature,
    collector_payload,
)
from migrations.p3_market_property_link import INDEXES, VALIDATORS


def matches(document, query):
    for key, wanted in query.items():
        actual = document.get(key)
        if isinstance(wanted, dict):
            if "$in" in wanted and actual not in wanted["$in"]:
                return False
            if "$ne" in wanted and actual == wanted["$ne"]:
                return False
            if "$regex" in wanted and not re.search(wanted["$regex"], str(actual or ""), re.I if wanted.get("$options") == "i" else 0):
                return False
        elif actual != wanted:
            return False
    return True


class Cursor:
    def __init__(self, documents):
        self.documents = list(documents)

    def sort(self, key, direction):
        self.documents.sort(key=lambda item: item.get(key) or "", reverse=direction < 0)
        return self

    def limit(self, count):
        self.documents = self.documents[:count]
        return self

    async def to_list(self, count):
        return self.documents[:count]


class Collection:
    def __init__(self, documents=None):
        self.documents = list(documents or [])

    async def find_one(self, query, projection=None, sort=None):
        found = [item for item in self.documents if matches(item, query)]
        if sort:
            key, direction = sort[0]
            found.sort(key=lambda item: item.get(key) or "", reverse=direction < 0)
        return dict(found[0]) if found else None

    def find(self, query, projection=None):
        return Cursor(dict(item) for item in self.documents if matches(item, query))

    async def update_one(self, query, update, upsert=False):
        document = next((item for item in self.documents if matches(item, query)), None)
        inserted = document is None
        if inserted:
            if not upsert:
                return None
            document = dict(query)
            self.documents.append(document)
        if inserted:
            document.update(update.get("$setOnInsert", {}))
        document.update(update.get("$set", {}))
        return None

    async def insert_one(self, document):
        self.documents.append(dict(document))

    async def count_documents(self, query):
        return sum(1 for item in self.documents if matches(item, query))


class Database:
    def __init__(self, **collections):
        self.collections = {name: Collection(documents) for name, documents in collections.items()}

    def __getattr__(self, name):
        return self.collections.setdefault(name, Collection())


PAYLOAD = {
    "source_site_id": "site-1", "source_listing_id": "ad-10",
    "source_url": "https://example.test/ad-10", "observed_at": "2026-08-20T01:00:00+00:00",
    "current_status": "ACTIVE", "transaction_type": "SALE",
    "property_type_id": "type-1", "property_type_name": "House",
    "province_id": "province-1", "city_id": "city-1", "suburb_id": "suburb-1",
    "province_name": "National Capital District", "city_name": "Port Moresby", "suburb_name": "Waigani",
    "street_name": "Waigani Drive", "lot": "15", "section": "42",
    "owner_name": "Test Owner", "bedrooms": 3, "bathrooms": 2,
    "price_amount": 900000, "price_type": "FIXED", "currency": "PGK",
    "raw_payload": {"title": "Waigani House"},
}


def linked_database(source=None):
    return Database(
        source_sites=[source or {"id": "site-1", "name": "Example", "domain": "example.test", "active": True, "is_trel_owned": False}],
        master_properties=[{"id": "property-1", "lifecycle_status": "active"}],
        property_addresses=[{"property_id": "property-1", "province_id": "province-1", "city_id": "city-1", "suburb_id": "suburb-1", "is_canonical": True, "valid_to": None}],
        property_parcels=[{"property_id": "property-1", "identifier_scheme": "URBAN_LOT_SECTION", "lot_norm": "15", "section_norm": "42", "street_norm": "WAIGANI DRIVE"}],
        parties=[{"id": "party-1", "normalized_name": "TEST OWNER"}],
        property_parties=[{"property_id": "property-1", "party_id": "party-1", "relationship_type": "OWNER"}],
    )


def test_market_link_schema_is_explicit_and_indexed():
    assert set(VALIDATORS) == {"source_sites", "source_listings", "source_listing_observations", "observation_prices", "property_match_reviews", "collection_runs"}
    assert any(name == "ix_source_master_link" for _, name, _, _ in INDEXES)
    assert any(name == "ix_subject_comparables" for _, name, _, _ in INDEXES)


def test_market_normalization_business_rules():
    assert monthly_equivalent(1000, "RENT", "WEEK") == 4333.33
    assert monthly_equivalent(900000, "SALE", None) is None
    assert effective_status("NOT_SEEN", "ACTIVE") == "RELISTED"
    assert effective_status("ACTIVE", "ACTIVE") == "ACTIVE"
    assert origin_kind({"domain": "trelpng.com"}) == "TREL_OWN"
    assert origin_kind({"domain": "hausples.com.pg"}) == "EXTERNAL"
    assert parcel_signature(PAYLOAD) == ("URBAN_LOT_SECTION", {"lot_norm": "15", "section_norm": "42", "street_norm": "WAIGANI DRIVE"})
    normalized = collector_payload("site-1", {"source_listing_id": "ad-1", "source_url": "https://example.test/ad-1", "purpose": "rent", "price": 1000, "rent_period": "weekly", "property_subtype": "House"})
    assert normalized["transaction_type"] == "RENT"
    assert normalized["rental_period"] == "WEEK"


def test_external_observation_links_to_advertised_master_and_preserves_history():
    async def run():
        db = linked_database()
        service = MarketPropertyLinkService(db)
        first = await service.ingest(dict(PAYLOAD), "staff-1")
        assert first["match"]["master_property_id"] == "property-1"
        assert first["source_listing"]["match_status"] == "MATCHED"
        assert first["observation"]["comparable_eligible"] is True
        assert len(db.source_listings.documents) == 1
        assert db.source_listing_observations.documents[0]["source_listing_id"] == first["source_listing"]["id"]

        not_seen = await service.ingest({**PAYLOAD, "observed_at": "2026-08-20T12:00:00+00:00", "current_status": "NOT_SEEN", "price_amount": None}, "staff-1")
        assert not_seen["source_listing"]["last_seen_at"] == "2026-08-20T01:00:00+00:00"
        assert not_seen["observation"]["priced_usable"] is False
        second = await service.ingest({**PAYLOAD, "observed_at": "2026-08-21T01:00:00+00:00"}, "staff-1")
        assert second["source_listing"]["id"] == first["source_listing"]["id"]
        assert second["source_listing"]["current_status"] == "RELISTED"
        assert len(db.source_listings.documents) == 1
        assert len(db.source_listing_observations.documents) == 3
    asyncio.run(run())


def test_missing_owner_requires_review_before_linking():
    async def run():
        db = linked_database()
        result = await MarketPropertyLinkService(db).match_master({**PAYLOAD, "owner_name": None})
        assert result["status"] == "REVIEW_REQUIRED"
        assert result["master_property_id"] is None
        assert result["candidates"] == ["property-1"]
    asyncio.run(run())


def test_trel_owned_observation_is_not_an_independent_comparable():
    async def run():
        db = linked_database({"id": "site-1", "name": "TRELPNG", "domain": "trelpng.com", "active": True, "is_trel_owned": True})
        result = await MarketPropertyLinkService(db).ingest({**PAYLOAD, "trel_property_id": "property-1"}, "staff-1")
        assert result["source_listing"]["origin_kind"] == "TREL_OWN"
        assert result["observation"]["comparable_eligible"] is False
        assert result["match"]["rule"] == "DIRECT_TREL_ID"
    asyncio.run(run())
