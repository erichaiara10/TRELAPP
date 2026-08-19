"""JWT auth, bcrypt password hashing, captcha, honeypot."""
import os
import random
import re
import string
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request

from core.db import db

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALG = os.environ.get("JWT_ALGORITHM", "HS256")

# Single-purpose token used only for the "must change password on first login"
# flow. Explicitly NOT an access token — cannot authenticate any regular API.
PWD_CHANGE_PURPOSE_FIRST_LOGIN = "first_login_password_change"
PWD_CHANGE_TOKEN_TTL_MINUTES = 10


def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()


def verify_password(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode(), h.encode())
    except Exception:
        return False


def create_access_token(user_id: str, email: str, role: str) -> str:
    payload = {
        "sub": user_id, "email": email, "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=12), "type": "access",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def create_password_change_token(user_id: str, purpose: str = PWD_CHANGE_PURPOSE_FIRST_LOGIN) -> str:
    """Single-purpose, short-lived token. NEVER accepted by get_current_user."""
    payload = {
        "sub": user_id,
        "type": "password_change",
        "purpose": purpose,
        "jti": uuid.uuid4().hex,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=PWD_CHANGE_TOKEN_TTL_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


async def decode_password_change_token(token: str, expected_purpose: str) -> dict:
    """Verify signature/expiry/purpose and confirm the jti has not been consumed."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(400, "Password change link expired. Please sign in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(400, "Invalid password change token.")
    if payload.get("type") != "password_change" or payload.get("purpose") != expected_purpose:
        raise HTTPException(400, "Invalid password change token.")
    jti = payload.get("jti")
    if not jti:
        raise HTTPException(400, "Invalid password change token.")
    if await db.used_password_change_tokens.find_one({"jti": jti}):
        raise HTTPException(400, "Password change link has already been used.")
    return payload


async def consume_password_change_token(jti: str, user_id: str) -> None:
    """Persist the jti so the same token cannot be replayed. TTL index cleans it up."""
    await db.used_password_change_tokens.insert_one({
        "jti": jti,
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc),
    })


# ---- Password strength ----
# Minimum 12 chars, at least one lowercase, uppercase, digit and special char.
PWD_MIN_LEN = 12
_PWD_SPECIAL_RE = re.compile(r"[^A-Za-z0-9]")


def password_strength_error(password: str) -> Optional[str]:
    """Return a user-facing message if the password is too weak, else None."""
    if not isinstance(password, str) or len(password) < PWD_MIN_LEN:
        return f"Password must be at least {PWD_MIN_LEN} characters long."
    if not re.search(r"[a-z]", password):
        return "Password must include at least one lowercase letter."
    if not re.search(r"[A-Z]", password):
        return "Password must include at least one uppercase letter."
    if not re.search(r"\d", password):
        return "Password must include at least one digit."
    if not _PWD_SPECIAL_RE.search(password):
        return "Password must include at least one special character."
    return None


# ---- Simple in-memory rate limiter (per IP + optional identifier) ----
# Suitable for a single-process dev/staging server. In production a shared
# store (Redis) would replace this.
_RATE_BUCKETS: dict = defaultdict(deque)


def rate_limit(key: str, max_hits: int, window_seconds: int) -> None:
    """Raise 429 if `key` has been hit more than max_hits within window_seconds."""
    now = time.time()
    bucket = _RATE_BUCKETS[key]
    cutoff = now - window_seconds
    while bucket and bucket[0] < cutoff:
        bucket.popleft()
    if len(bucket) >= max_hits:
        raise HTTPException(429, "Too many attempts. Please wait a few minutes and try again.")
    bucket.append(now)


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
    # Hardening: single-purpose password-change tokens must NEVER unlock regular APIs.
    if payload.get("type") != "access":
        raise HTTPException(401, "Invalid token type")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(401, "User not found")
    return user


def require_roles(*roles: str):
    async def _dep(user: dict = Depends(get_current_user)):
        if user["role"] != "system_admin" and user["role"] not in roles:
            raise HTTPException(403, "Forbidden")
        return user
    return _dep


# ---- Human verification (captcha + honeypot) ----
# Exclude visually confusable characters (0/O, 1/I/l)
_CAPTCHA_ALPHABET = (
    string.ascii_uppercase.replace("O", "").replace("I", "")
    + string.digits.replace("0", "").replace("1", "")
)


def captcha_pair():
    code = "".join(random.choices(_CAPTCHA_ALPHABET, k=5))
    return f"Type these letters/numbers: {code}", code


def captcha_encode(answer: str) -> str:
    payload = {"a": answer, "type": "captcha",
               "exp": datetime.now(timezone.utc) + timedelta(minutes=15)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def captcha_verify(token: Optional[str], answer: Optional[str]) -> None:
    if not token or answer is None:
        raise HTTPException(400, "Human verification required")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(400, "Verification expired — please retry")
    except jwt.InvalidTokenError:
        raise HTTPException(400, "Invalid verification token")
    if payload.get("type") != "captcha":
        raise HTTPException(400, "Invalid verification token type")
    if str(answer).strip().upper() != str(payload.get("a", "")).strip().upper():
        raise HTTPException(400, "Incorrect verification — please try again")


def honeypot_check(hp: Optional[str]) -> None:
    if hp:
        raise HTTPException(400, "Bot detected")
