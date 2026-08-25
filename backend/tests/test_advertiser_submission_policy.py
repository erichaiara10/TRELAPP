import asyncio
import sys
import types

try:
    from fastapi import HTTPException
except ModuleNotFoundError:
    class HTTPException(Exception):
        def __init__(self, status_code, detail):
            self.status_code = status_code
            self.detail = detail

    fastapi_stub = types.ModuleType("fastapi")
    fastapi_stub.Depends = lambda dependency: dependency
    fastapi_stub.HTTPException = HTTPException
    sys.modules["fastapi"] = fastapi_stub

    db_stub = types.ModuleType("core.db")
    db_stub.db = None
    sys.modules["core.db"] = db_stub

    security_stub = types.ModuleType("core.security")
    security_stub.get_current_user = lambda: None
    sys.modules["core.security"] = security_stub

import core.account_policy as policy


class _Collection:
    def __init__(self, records):
        self.records = records

    async def find_one(self, query, projection=None):
        for record in self.records:
            if all(
                record.get(key) in value["$in"] if isinstance(value, dict) and "$in" in value
                else record.get(key) == value
                for key, value in query.items()
            ):
                return dict(record)
        return None


class _DB:
    def __init__(self, identity_status=None):
        self.advertiser_profiles = _Collection([{
            "id": "profile-1", "user_id": "advertiser-1",
            "relationship_type": "OWNER", "status": "PENDING",
        }])
        documents = [] if identity_status is None else [{
            "id": "identity-1", "user_id": "advertiser-1",
            "document_type": "NID_CARD", "status": identity_status,
        }]
        self.identity_documents = _Collection(documents)


USER = {
    "id": "advertiser-1", "status": "ACTIVE",
    "account_category": "PROPERTY_ADVERTISER",
}


def _run_with_db(identity_status, action):
    original = policy.db
    policy.db = _DB(identity_status)
    try:
        return action()
    finally:
        policy.db = original


def test_submitted_identity_allows_property_to_enter_staff_review():
    for status in ("PENDING", "PENDING_REVIEW", "UNDER_REVIEW", "VERIFIED"):
        result = _run_with_db(
            status, lambda: asyncio.run(policy.require_property_submitter(USER))
        )
        assert result == USER


def test_missing_or_rejected_identity_blocks_property_submission():
    for status in (None, "REJECTED"):
        def attempt():
            try:
                asyncio.run(policy.require_property_submitter(USER))
            except HTTPException as exc:
                assert exc.status_code == 403
                assert "Submit one government-issued identity document" in str(exc.detail)
                return
            raise AssertionError("Submission was allowed without an acceptable identity document")
        _run_with_db(status, attempt)


def test_pending_identity_still_cannot_write_established_property_records():
    def attempt():
        try:
            asyncio.run(policy.require_property_writer(USER))
        except HTTPException as exc:
            assert exc.status_code == 403
            return
        raise AssertionError("Pending identity was allowed to write an established property")
    _run_with_db("PENDING", attempt)
