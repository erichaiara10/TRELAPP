"""JWT auth, bcrypt password hashing, captcha, honeypot."""
import os
import random
import string
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request

from core.db import db

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALG = os.environ.get("JWT_ALGORITHM", "HS256")


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
