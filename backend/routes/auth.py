"""Auth (login/logout/me) + Users CRUD."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from core.db import db, new_id, now_iso
from core.security import (
    PWD_CHANGE_PURPOSE_FIRST_LOGIN,
    client_ip,
    consume_password_change_token,
    create_access_token,
    create_password_change_token,
    decode_password_change_token,
    get_current_user,
    hash_password,
    password_strength_error,
    rate_limit,
    require_roles,
    verify_password,
)
from models import LoginIn, PasswordUpdate, UserCreate, UserUpdate

router = APIRouter()


class FirstLoginPasswordChangeIn(BaseModel):
    token: str = Field(..., min_length=10)
    new_password: str = Field(..., min_length=1)
    confirm_password: str = Field(..., min_length=1)


_GENERIC_LOGIN_ERROR = "Invalid email or password"


async def _pa_audit(event_type: str, user_id: str, extras: dict | None = None) -> None:
    """Write a password-lifecycle audit event. No secrets ever recorded."""
    doc = {
        "id": new_id(),
        "record_type": "user",
        "reference": user_id,
        "action": event_type,
        "previous_status": None,
        "new_status": None,
        "performed_by_id": user_id,
        "created_at": now_iso(),
        "metadata": {k: v for k, v in (extras or {}).items() if k not in ("password", "token", "new_password")},
    }
    await db.pa_audit.insert_one(doc)


@router.post("/auth/login")
async def login(payload: LoginIn, request: Request, response: Response):
    email = payload.email.lower().strip()
    ip = client_ip(request)
    # Rate-limit brute-force by (ip, email) — 8 attempts / 15 min.
    rate_limit(f"login:{ip}:{email}", max_hits=8, window_seconds=900)

    user = await db.users.find_one({"email": email})
    if not user or not verify_password(payload.password, user.get("password_hash", "")):
        raise HTTPException(401, _GENERIC_LOGIN_ERROR)

    # If the user is flagged for a mandatory password change, do NOT issue an
    # access token. Instead return a short-lived single-purpose token that can
    # only be redeemed by /auth/change-password-first-login.
    if user.get("must_change_password") is True:
        change_token = create_password_change_token(
            user["id"], purpose=PWD_CHANGE_PURPOSE_FIRST_LOGIN,
        )
        await _pa_audit("password_change_required_challenge_issued", user["id"])
        return {
            "password_change_required": True,
            "purpose": PWD_CHANGE_PURPOSE_FIRST_LOGIN,
            "change_token": change_token,
            "expires_in_seconds": 600,
            # No access token, no role, no name — client only needs to route to
            # the forced password-change screen.
            "email": user["email"],
        }

    token = create_access_token(user["id"], user["email"], user["role"])
    response.set_cookie("access_token", token, httponly=True, secure=False,
                        samesite="lax", max_age=43200, path="/")
    return {"id": user["id"], "email": user["email"], "name": user["name"],
            "role": user["role"], "token": token}


@router.post("/auth/change-password-first-login")
async def change_password_first_login(
    payload: FirstLoginPasswordChangeIn, request: Request, response: Response,
):
    ip = client_ip(request)
    # Rate-limit the change endpoint on the client IP — 10 attempts / 15 min.
    rate_limit(f"pwd-change:{ip}", max_hits=10, window_seconds=900)

    # Verify signature, purpose, expiry AND single-use replay protection.
    decoded = await decode_password_change_token(
        payload.token, expected_purpose=PWD_CHANGE_PURPOSE_FIRST_LOGIN,
    )

    if payload.new_password != payload.confirm_password:
        raise HTTPException(400, "New password and confirmation do not match.")

    strength_err = password_strength_error(payload.new_password)
    if strength_err:
        raise HTTPException(400, strength_err)

    user = await db.users.find_one({"id": decoded["sub"]})
    if not user:
        raise HTTPException(400, "Account not found.")

    # Reject reuse of the temporary password.
    if verify_password(payload.new_password, user.get("password_hash", "")):
        raise HTTPException(
            400,
            "New password must be different from your temporary password.",
        )

    # Atomically update hash + clear the must_change_password flag.
    # Bump password_version so any legacy access tokens (if ever issued) are
    # rejected on next use — defence in depth. Not strictly needed today
    # because the login route never issues an access token when the flag is set.
    new_hash = hash_password(payload.new_password)
    result = await db.users.update_one(
        {
            "id": user["id"],
            # Prevent double-execution racing another concurrent request.
            "must_change_password": True,
        },
        {
            "$set": {
                "password_hash": new_hash,
                "must_change_password": False,
                "password_changed_at": now_iso(),
            },
            "$inc": {"password_version": 1},
        },
    )
    if result.modified_count != 1:
        # Another request already consumed the flag OR the user is not eligible.
        raise HTTPException(400, "Password change is no longer required for this account.")

    # Mark the token jti as consumed → any replay attempt is now blocked.
    await consume_password_change_token(decoded["jti"], user["id"])

    # Invalidate any existing sessions by clearing the cookie on this response.
    # (Cookies are per-response only; there is no server-side session store
    # today. Bumping password_version provides the server-side signal for
    # future access-token-versioning if we choose to add it.)
    response.delete_cookie("access_token", path="/")

    await _pa_audit("password_changed_first_login", user["id"], extras={
        "jti": decoded["jti"],
        "ip": ip,
    })

    return {
        "ok": True,
        "message": "Password updated. Please sign in with your new password.",
    }


@router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}


@router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user


@router.get("/users")
async def list_users(user: dict = Depends(get_current_user)):
    return await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(500)


@router.post("/users")
async def create_user(payload: UserCreate, user: dict = Depends(require_roles("system_admin"))):
    email = payload.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Email already registered")
    u = {"id": new_id(), "email": email, "name": payload.name, "role": payload.role,
         "phone": payload.phone, "password_hash": hash_password(payload.password),
         "created_at": now_iso()}
    await db.users.insert_one(u)
    u.pop("password_hash", None); u.pop("_id", None)
    return u


@router.delete("/users/{uid}")
async def delete_user(uid: str, user: dict = Depends(require_roles("system_admin"))):
    if uid == user["id"]:
        raise HTTPException(400, "Cannot delete self")
    await db.users.delete_one({"id": uid})
    return {"ok": True}


@router.put("/users/{uid}")
async def update_user(uid: str, payload: UserUpdate,
                      user: dict = Depends(require_roles("system_admin"))):
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if "email" in updates:
        email = updates["email"].lower().strip()
        clash = await db.users.find_one({"email": email, "id": {"$ne": uid}})
        if clash:
            raise HTTPException(400, "Email already in use")
        updates["email"] = email
    if not updates:
        raise HTTPException(400, "No changes provided")
    await db.users.update_one({"id": uid}, {"$set": updates})
    return await db.users.find_one({"id": uid}, {"_id": 0, "password_hash": 0})


@router.put("/users/{uid}/password")
async def reset_user_password(uid: str, payload: PasswordUpdate,
                              user: dict = Depends(require_roles("system_admin"))):
    if len(payload.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    await db.users.update_one({"id": uid}, {"$set": {"password_hash": hash_password(payload.password)}})
    return {"ok": True}
