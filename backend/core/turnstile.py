"""Cloudflare Turnstile verification.

Verifies the client-side widget token via
`POST https://challenges.cloudflare.com/turnstile/v0/siteverify`.

If TURNSTILE_SECRET_KEY is not set, verification is SKIPPED (dev/local mode).
Cloudflare's sitewide test keys (1x0000000000000000000000000000000AA →
always passes; 2x0000000000000000000000000000000AA → always fails) allow
end-to-end testing without registering a real Turnstile site.
"""
from __future__ import annotations

import os
from typing import Optional

import httpx


VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


async def verify_turnstile(token: Optional[str], remote_ip: Optional[str] = None) -> bool:
    secret = os.getenv("TURNSTILE_SECRET_KEY", "").strip()
    if not secret:
        # No secret configured — treat as verification disabled (dev bypass).
        return True
    if not token:
        return False
    payload = {"secret": secret, "response": token}
    if remote_ip:
        payload["remoteip"] = remote_ip
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(VERIFY_URL, data=payload)
            data = response.json()
            return bool(data.get("success"))
    except Exception:
        # Fail closed: any network / parse error rejects the challenge.
        return False
