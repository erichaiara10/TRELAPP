"""Login brute-force guard: 5 attempts / 15-minute rolling window per (email, IP).

Backed by the `login_failures` collection (uses a TTL index on `occurred_at`).
Kept intentionally simple — no distributed cache dependency. Successful login
must call `reset()` to clear the counter for that (email, IP).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from core.db import db, now_iso

MAX_ATTEMPTS = int(os.getenv("TREL_LOGIN_MAX_ATTEMPTS", "5"))
WINDOW_SECONDS = int(os.getenv("TREL_LOGIN_WINDOW_SECONDS", str(15 * 60)))


async def ensure_indexes() -> None:
    """Called once at startup — TTL index automatically prunes expired counters."""
    await db.login_failures.create_index("occurred_at", expireAfterSeconds=WINDOW_SECONDS * 2)
    await db.login_failures.create_index([("email", 1), ("ip", 1)])


def _window_start() -> datetime:
    return datetime.now(timezone.utc) - timedelta(seconds=WINDOW_SECONDS)


def _key(email: str, ip: Optional[str]) -> dict:
    return {"email": (email or "").lower().strip(), "ip": ip or "unknown"}


async def is_locked(email: str, ip: Optional[str]) -> bool:
    """Locked if EITHER the (email, ip) key OR the email-alone counter exceeds threshold.

    Behind a k8s ingress the caller IP rotates across proxy pods, so keying
    only on IP defeats the guard. We therefore also enforce an email-wide
    counter so no single account can be brute-forced regardless of which pod
    fielded each attempt.
    """
    window = _window_start().isoformat()
    by_ip = await db.login_failures.count_documents({**_key(email, ip), "occurred_at": {"$gte": window}})
    if by_ip >= MAX_ATTEMPTS:
        return True
    by_email = await db.login_failures.count_documents({"email": (email or "").lower().strip(), "occurred_at": {"$gte": window}})
    return by_email >= MAX_ATTEMPTS


async def record_failure(email: str, ip: Optional[str]) -> None:
    doc = {**_key(email, ip), "occurred_at": now_iso()}
    await db.login_failures.insert_one(doc)


async def reset(email: str, ip: Optional[str]) -> None:
    # Reset the whole email counter — success from any pod clears every pod's tally.
    await db.login_failures.delete_many({"email": (email or "").lower().strip()})
