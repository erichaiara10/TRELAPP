"""Shared Mongo client + tiny helpers."""
import os
import uuid
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "trel_db")

MONGO_USERNAME = os.getenv("MONGO_USERNAME")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD")
MONGO_AUTH_DATABASE = os.getenv("MONGO_AUTH_DATABASE", "admin")

_client_options = {}
if MONGO_USERNAME:
    _client_options.update(
        username=MONGO_USERNAME,
        password=MONGO_PASSWORD,
        authSource=MONGO_AUTH_DATABASE,
    )

client = AsyncIOMotorClient(MONGO_URL, **_client_options)
db = client[DB_NAME]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


def strip_id(doc):
    if doc:
        doc.pop("_id", None)
    return doc
