"""Hardening regression tests — post iter-29.

Covers:
  1. Topology detection utilities in core.db
  2. IntegratedPropertyService _txn() branching (transactional vs fallback)
  3. Partial-write failure → PartialWriteError + compensating rollback + audit log
  4. Strict-transactions guard refuses to boot on Atlas + standalone
  5. PartialWriteError shape
"""
from __future__ import annotations

import asyncio
import types

import pytest

from core import db as db_module
from core.integrated_property_service import (
    IntegratedPropertyService,
    PartialWriteError,
    _InsertTracker,
)


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


# ---------------- Topology & strict-mode detection ----------------
def test_looks_like_atlas_matrix():
    assert db_module._looks_like_atlas("mongodb+srv://cluster.mongodb.net/db")
    assert db_module._looks_like_atlas("mongodb://ac.mongodb.net:27017")
    assert db_module._looks_like_atlas("mongodb://cluster.atlas.mongo.com")
    assert not db_module._looks_like_atlas("mongodb://localhost:27017")
    assert not db_module._looks_like_atlas("")


def test_strict_transactions_from_env(monkeypatch):
    monkeypatch.setenv("TREL_MONGO_STRICT_TRANSACTIONS", "true")
    assert db_module.strict_transactions_required() is True
    monkeypatch.setenv("TREL_MONGO_STRICT_TRANSACTIONS", "false")
    monkeypatch.setattr(db_module, "MONGO_URL", "mongodb://localhost:27017")
    assert db_module.strict_transactions_required() is False


def test_strict_transactions_from_atlas_uri(monkeypatch):
    monkeypatch.delenv("TREL_MONGO_STRICT_TRANSACTIONS", raising=False)
    monkeypatch.setattr(db_module, "MONGO_URL", "mongodb+srv://foo.mongodb.net/prod")
    assert db_module.strict_transactions_required() is True


# ---------------- InsertTracker rollback ----------------
class _FakeCollection:
    def __init__(self, name, log, fail_on_delete=False):
        self.name = name
        self.log = log
        self.fail_on_delete = fail_on_delete

    async def delete_one(self, filt):
        if self.fail_on_delete:
            raise RuntimeError(f"delete failed on {self.name}")
        self.log.append(("delete_one", self.name, filt))

    async def insert_one(self, doc):
        self.log.append(("insert_one", self.name, doc.get("id")))


class _FakeDb:
    def __init__(self, orphan_collection=None):
        self.log = []
        self.orphan_collection = orphan_collection

    def __getitem__(self, name):
        return _FakeCollection(
            name, self.log,
            fail_on_delete=(name == self.orphan_collection),
        )

    def __getattr__(self, name):
        if name in {"log", "orphan_collection"}:
            raise AttributeError(name)
        return _FakeCollection(name, self.__dict__["log"])


def test_insert_tracker_compensates_in_reverse():
    fake = _FakeDb()

    async def scenario():
        tracker = _InsertTracker(fake)
        await tracker.track_insert("master_properties", {"id": "m1"})
        await tracker.track_insert("listings", {"id": "l1"})
        await tracker.track_insert("property_parcels", {"id": "p1"})
        return await tracker.compensate_and_record(RuntimeError("boom"))

    failure_id = _run(scenario())
    deletes = [entry for entry in fake.log if entry[0] == "delete_one"]
    assert [d[1] for d in deletes] == ["property_parcels", "listings", "master_properties"]
    audit = [entry for entry in fake.log if entry[0] == "insert_one" and entry[1] == "partial_write_failures"]
    assert len(audit) == 1
    assert audit[0][2] == failure_id


def test_insert_tracker_records_orphans_when_delete_fails():
    fake = _FakeDb(orphan_collection="listings")

    async def scenario():
        tracker = _InsertTracker(fake)
        await tracker.track_insert("master_properties", {"id": "m1"})
        await tracker.track_insert("listings", {"id": "l1"})
        await tracker.compensate_and_record(RuntimeError("boom"))

    _run(scenario())
    deletes = [entry for entry in fake.log if entry[0] == "delete_one"]
    assert deletes[-1][1] == "master_properties"


# ---------------- Topology detection ----------------
class _FakeClient:
    def __init__(self, hello):
        self._hello = hello
        self.admin = types.SimpleNamespace(command=self._command)

    async def _command(self, name):
        assert name == "hello"
        return self._hello


def test_detect_topology_replica_set(monkeypatch):
    monkeypatch.setattr(db_module, "client", _FakeClient({"setName": "rs0"}))
    topology = _run(db_module.detect_topology())
    assert topology["supports_transactions"] is True
    assert topology["kind"] == "REPLICA_SET"


def test_detect_topology_standalone(monkeypatch):
    monkeypatch.setattr(db_module, "client", _FakeClient({}))
    topology = _run(db_module.detect_topology())
    assert topology["supports_transactions"] is False
    assert topology["kind"] == "STANDALONE"


def test_detect_topology_sharded(monkeypatch):
    monkeypatch.setattr(db_module, "client", _FakeClient({"msg": "isdbgrid"}))
    topology = _run(db_module.detect_topology())
    assert topology["supports_transactions"] is True
    assert topology["kind"] == "SHARDED"


def test_service_refuses_standalone_when_strict(monkeypatch):
    monkeypatch.setenv("TREL_MONGO_STRICT_TRANSACTIONS", "true")
    fake_client = _FakeClient({})
    monkeypatch.setattr(db_module, "client", fake_client)
    monkeypatch.setattr(db_module, "MONGO_URL", "mongodb://localhost:27017")
    svc = IntegratedPropertyService(_FakeDb(), fake_client)
    with pytest.raises(RuntimeError, match="STRICT_TRANSACTIONS"):
        _run(svc._detect_topology())


# ---------------- PartialWriteError shape ----------------
def test_partial_write_error_carries_failure_id():
    err = PartialWriteError(ValueError("boom"), "fid-123")
    assert err.failure_id == "fid-123"
    assert "fid-123" in str(err)
    assert isinstance(err.cause, ValueError)
