"""Shared Mongo client + tiny helpers."""
import os
import uuid
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.getenv("DB_NAME", "trel_db")

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


def strip_id(doc):
    if doc:
        doc.pop("_id", None)
    return doc
