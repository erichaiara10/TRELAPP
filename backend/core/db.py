"""Shared Mongo client + tiny helpers."""
import logging
import os
import re
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

_TOPOLOGY_LOGGER = logging.getLogger("trel")


def _looks_like_atlas(uri: str) -> bool:
    """Detect Atlas / managed-cluster URIs where transactions must be available."""
    lowered = (uri or "").lower()
    return (
        "+srv://" in lowered
        or bool(re.search(r"\.mongodb\.net(\b|/|:)", lowered))
        or "atlas" in lowered
    )


def strict_transactions_required() -> bool:
    """Return True when the deployment refuses non-transactional fallback."""
    env_flag = os.getenv("TREL_MONGO_STRICT_TRANSACTIONS", "").strip().lower() in {"1", "true", "yes"}
    return env_flag or _looks_like_atlas(MONGO_URL)


async def detect_topology() -> dict:
    """Probe MongoDB topology once. Returns {kind, supports_transactions, set_name}."""
    try:
        info = await client.admin.command("hello")
    except Exception as exc:
        _TOPOLOGY_LOGGER.warning("MongoDB topology probe failed: %s", exc)
        return {"kind": "UNKNOWN", "supports_transactions": False, "set_name": None, "probe_error": str(exc)}
    if info.get("setName"):
        return {"kind": "REPLICA_SET", "supports_transactions": True, "set_name": info["setName"]}
    if info.get("msg") == "isdbgrid":
        return {"kind": "SHARDED", "supports_transactions": True, "set_name": None}
    return {"kind": "STANDALONE", "supports_transactions": False, "set_name": None}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


def strip_id(doc):
    if doc:
        doc.pop("_id", None)
    return doc
