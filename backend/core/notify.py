"""Simple in-DB notification log + agent auto-assignment helper."""
from typing import Optional

from core.db import db, now_iso, new_id


async def auto_assign_agent(prefer_role: str = "sales_agent") -> Optional[str]:
    agent = await db.users.find_one({"role": prefer_role}, {"_id": 0, "id": 1})
    return agent["id"] if agent else None


async def notify(subject: str, body: str, to: Optional[str] = None):
    n = {
        "id": new_id(), "kind": "email_sim", "to": to,
        "subject": subject, "body": body, "read": False, "created_at": now_iso(),
    }
    await db.notifications.insert_one(n)
