"""Auth (login/logout/me/registration/password reset) + Users CRUD."""
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field

from core.account_policy import account_category, require_staff, workspace_path
from core.db import db, new_id, now_iso
from core.login_guard import is_locked, record_failure, reset as reset_login_failures
from core.notify import notify
from core.security import (
    create_access_token, get_current_user, hash_password,
    require_roles, verify_password,
)
from core.turnstile import verify_turnstile
from models import LoginIn, PasswordUpdate, UserCreate, UserUpdate

router = APIRouter()


class PublicRegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str = Field(min_length=5, max_length=40)
    password: str = Field(min_length=8, max_length=128)
    account_category: Literal["PROPERTY_ADVERTISER", "REFERRAL_PARTNER"]
    advertiser_relationship_type: Optional[Literal[
        "OWNER", "JOINT_OWNER", "AUTHORISED_AGENT", "AUTHORISED_REPRESENTATIVE"
    ]] = None
    turnstile_token: Optional[str] = None


class ForgotPasswordIn(BaseModel):
    email: EmailStr
    turnstile_token: Optional[str] = None


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=20, max_length=256)
    password: str = Field(min_length=8, max_length=128)


class GoogleAuthIn(BaseModel):
    access_token: str = Field(min_length=20, max_length=4096)
    mode: Literal["login", "register"]
    phone: Optional[str] = Field(default=None, min_length=5, max_length=40, pattern=r"^\\+?[0-9\\s-]{5,40}$")
    advertiser_relationship_type: Optional[Literal[
        "OWNER", "JOINT_OWNER", "AUTHORISED_AGENT", "AUTHORISED_REPRESENTATIVE"
    ]] = None
    terms_accepted: bool = False


class SelfProfileUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    phone: Optional[str] = Field(default=None, min_length=5, max_length=40)
    preferred_communication: Optional[Literal["WhatsApp", "Email", "Both"]] = None
    residential_address: Optional[str] = Field(default=None, max_length=300)
    business_name: Optional[str] = Field(default=None, max_length=160)
    ipa_registration_number: Optional[str] = Field(default=None, max_length=80)
    position: Optional[str] = Field(default=None, max_length=120)
    business_phone: Optional[str] = Field(default=None, max_length=40, pattern=r"^\\+?[0-9\\s-]{5,40}$")
    notification_preferences: Optional[dict[str, bool]] = None
    profile_photo_url: Optional[str] = Field(default=None, max_length=1000)


class IdentityDocumentIn(BaseModel):
    document_type: Literal["Passport", "Driver Licence", "National Identification Card"]
    file_name: str = Field(min_length=1, max_length=255)
    url: str = Field(min_length=1, max_length=1000)


STAFF_ROLES = {
    "system_admin", "managing_director", "sales_manager", "sales_agent",
    "leasing_agent", "property_manager", "marketing_officer",
}


def _validate_account_role(category: str, role: str) -> None:
    allowed = {
        "STAFF": STAFF_ROLES,
        "PROPERTY_ADVERTISER": {"property_advertiser"},
        "REFERRAL_PARTNER": {"referral_partner"},
    }
    if role not in allowed[category]:
        raise HTTPException(400, f"Role '{role}' is not valid for {category}")


def _validate_advertiser_relationship(category: str, relationship: str | None) -> None:
    if category == "PROPERTY_ADVERTISER" and relationship not in {
        "OWNER", "JOINT_OWNER", "AUTHORISED_AGENT", "AUTHORISED_REPRESENTATIVE",
    }:
        raise HTTPException(400, "Property Advertiser relationship type is required")


async def _verified_google_identity(access_token: str) -> dict:
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    if not client_id:
        raise HTTPException(503, "Google authentication is not configured")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            token_response = await client.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"access_token": access_token},
            )
            token_response.raise_for_status()
            token_data = token_response.json()
            if token_data.get("aud") != client_id:
                raise HTTPException(401, "Google authentication failed")
            profile_response = await client.get(
                "https://openidconnect.googleapis.com/v1/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            profile_response.raise_for_status()
            profile = profile_response.json()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(401, "Google authentication failed")
    if not profile.get("sub") or not profile.get("email") or not profile.get("email_verified"):
        raise HTTPException(401, "Google account email is not verified")
    return profile


def _google_session(user: dict, response: Response) -> dict:
    token = create_access_token(user["id"], user["email"], user["role"])
    response.set_cookie("access_token", token, httponly=True, secure=False,
                        samesite="lax", max_age=43200, path="/")
    return {
        "id": user["id"], "email": user["email"], "name": user["name"],
        "role": user["role"], "account_category": account_category(user),
        "workspace_path": workspace_path(user), "token": token,
    }


@router.post("/auth/login")
async def login(payload: LoginIn, request: Request, response: Response):
    email = payload.email.lower().strip()
    fwd = request.headers.get("x-forwarded-for", "")
    ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else None)
    # Cloudflare Turnstile — passing is enforced when TURNSTILE_SECRET_KEY is set.
    if not await verify_turnstile(getattr(payload, "turnstile_token", None), ip):
        raise HTTPException(400, "Human verification failed. Please retry the check.")
    if await is_locked(email, ip):
        raise HTTPException(429, "Too many login attempts. Try again later.")
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(payload.password, user.get("password_hash", "")):
        await record_failure(email, ip)
        raise HTTPException(401, "Invalid email or password")
    if user.get("status", "ACTIVE") != "ACTIVE":
        raise HTTPException(403, "Account is not active")
    await reset_login_failures(email, ip)
    token = create_access_token(user["id"], user["email"], user["role"])
    response.set_cookie("access_token", token, httponly=True, secure=False,
                        samesite="lax", max_age=43200, path="/")
    return {"id": user["id"], "email": user["email"], "name": user["name"],
            "role": user["role"], "account_category": account_category(user),
            "workspace_path": workspace_path(user), "token": token}


@router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}


@router.get("/auth/google/config")
async def google_config():
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    return {"enabled": bool(client_id), "client_id": client_id}


@router.post("/auth/google")
async def google_auth(payload: GoogleAuthIn, response: Response):
    identity = await _verified_google_identity(payload.access_token)
    email = identity["email"].lower().strip()
    google_sub = identity["sub"]
    user = await db.users.find_one({"$or": [{"google_sub": google_sub}, {"email": email}]})

    if user:
        if user.get("google_sub") not in {None, google_sub}:
            raise HTTPException(409, "This email is linked to another Google account")
        if user.get("status", "ACTIVE") != "ACTIVE":
            raise HTTPException(403, "Account is not active")
        await db.users.update_one(
            {"id": user["id"]},
            {"$set": {
                "google_sub": google_sub,
                "google_email_verified": True,
                "google_linked_at": now_iso(),
            }},
        )
        return _google_session(user, response)

    if payload.mode != "register":
        raise HTTPException(404, "No TRELPNG account was found. Use Create Account first.")
    if not payload.phone or len(payload.phone.strip()) < 5:
        raise HTTPException(400, "Mobile number is required")
    if not payload.terms_accepted:
        raise HTTPException(400, "Accept the Terms of Use and Privacy Policy")
    _validate_advertiser_relationship("PROPERTY_ADVERTISER", payload.advertiser_relationship_type)

    user = {
        "id": new_id(), "email": email,
        "name": (identity.get("name") or email.split("@")[0]).strip(),
        "phone": (payload.phone or "").strip(),
        "role": "property_advertiser", "account_category": "PROPERTY_ADVERTISER",
        "status": "ACTIVE", "auth_provider": "google", "google_sub": google_sub,
        "google_email_verified": True, "created_at": now_iso(),
    }
    await db.users.insert_one(user)
    await db.advertiser_profiles.insert_one({
        "id": new_id(), "user_id": user["id"],
        "relationship_type": payload.advertiser_relationship_type,
        "status": "PENDING", "created_at": now_iso(), "updated_at": now_iso(),
    })
    return _google_session(user, response)


@router.post("/auth/register", status_code=201)
async def public_register(payload: PublicRegisterIn, request: Request):
    fwd = request.headers.get("x-forwarded-for", "")
    ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else None)
    if not await verify_turnstile(payload.turnstile_token, ip):
        raise HTTPException(400, "Human verification failed. Please retry the check.")
    """Self-registration for the two approved external account categories only."""
    email = payload.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Email already registered")
    _validate_advertiser_relationship(payload.account_category, payload.advertiser_relationship_type)
    role = "property_advertiser" if payload.account_category == "PROPERTY_ADVERTISER" else "referral_partner"
    user = {
        "id": new_id(), "email": email, "name": payload.name.strip(), "phone": payload.phone.strip(),
        "role": role, "account_category": payload.account_category, "status": "ACTIVE",
        "password_hash": hash_password(payload.password), "created_at": now_iso(),
    }
    await db.users.insert_one(user)
    if payload.account_category == "PROPERTY_ADVERTISER":
        await db.advertiser_profiles.insert_one({
            "id": new_id(), "user_id": user["id"],
            "relationship_type": payload.advertiser_relationship_type,
            "status": "PENDING", "created_at": now_iso(), "updated_at": now_iso(),
        })
    else:
        await db.referral_partner_profiles.insert_one({
            "id": new_id(), "user_id": user["id"], "status": "ACTIVE",
            "created_at": now_iso(), "updated_at": now_iso(),
        })
    return {"ok": True, "account_category": payload.account_category, "login_path": "/add-property?auth=login"}


async def _send_password_reset_email(email: str, reset_url: str) -> None:
    subject = "Reset your TRELPNG password"
    body = (
        "A password reset was requested for your TRELPNG account. "
        f"Use this secure link within 30 minutes: {reset_url}"
    )
    await notify(subject, body, email)
    api_key = os.environ.get("RESEND_API_KEY")
    sender = os.environ.get("RESEND_FROM_EMAIL", "TRELPNG <noreply@trelpng.com>")
    if not api_key:
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "from": sender,
                    "to": [email],
                    "subject": subject,
                    "html": (
                        "<p>A password reset was requested for your TRELPNG account.</p>"
                        f'<p><a href="{reset_url}">Reset your password</a></p>'
                        "<p>This secure link expires in 30 minutes.</p>"
                    ),
                },
            )
            response.raise_for_status()
    except Exception:
        # Keep the public response account-neutral; the in-app notification log
        # preserves the reset link for test-environment verification.
        return


@router.post("/auth/forgot-password")
async def forgot_password(payload: ForgotPasswordIn, request: Request):
    fwd = request.headers.get("x-forwarded-for", "")
    ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else None)
    if not await verify_turnstile(payload.turnstile_token, ip):
        raise HTTPException(400, "Human verification failed. Please retry the check.")
    email = payload.email.lower().strip()
    user = await db.users.find_one({"email": email}, {"_id": 0, "id": 1})
    if user:
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        await db.password_reset_tokens.delete_many({"user_id": user["id"]})
        await db.password_reset_tokens.insert_one({
            "id": new_id(),
            "user_id": user["id"],
            "token_hash": token_hash,
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=30),
            "created_at": now_iso(),
        })
        public_url = os.environ.get("PUBLIC_APP_URL") or str(request.base_url).rstrip("/")
        reset_url = f"{public_url}/add-property?auth=reset&token={raw_token}"
        await _send_password_reset_email(email, reset_url)
    return {"ok": True, "message": "If that email is registered, a reset link has been sent."}


@router.post("/auth/reset-password")
async def reset_password(payload: ResetPasswordIn):
    token_hash = hashlib.sha256(payload.token.encode()).hexdigest()
    reset = await db.password_reset_tokens.find_one({
        "token_hash": token_hash,
        "expires_at": {"$gt": datetime.now(timezone.utc)},
    })
    if not reset:
        raise HTTPException(400, "This password-reset link is invalid or has expired.")
    await db.users.update_one(
        {"id": reset["user_id"]},
        {"$set": {"password_hash": hash_password(payload.password)}},
    )
    await db.password_reset_tokens.delete_many({"user_id": reset["user_id"]})
    return {"ok": True}


@router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    output = {**user, "account_category": account_category(user), "workspace_path": workspace_path(user)}
    output.pop("password_hash", None)
    output.pop("_id", None)
    if account_category(user) == "PROPERTY_ADVERTISER":
        profile = await db.advertiser_profiles.find_one({"user_id": user["id"]}, {"_id": 0}) or {}
        output["advertiser_profile"] = profile
        output["identity_documents"] = await db.identity_documents.find(
            {"user_id": user["id"]}, {"_id": 0}
        ).sort("created_at", -1).to_list(20)
    return output


@router.put("/auth/me")
async def update_me(payload: SelfProfileUpdate, user: dict = Depends(get_current_user)):
    values = payload.model_dump(exclude_none=True)
    user_updates = {key: values.pop(key) for key in ("name", "phone") if key in values}
    if user_updates:
        await db.users.update_one({"id": user["id"]}, {"$set": user_updates})
    if values and account_category(user) == "PROPERTY_ADVERTISER":
        await db.advertiser_profiles.update_one(
            {"user_id": user["id"]},
            {"$set": {**values, "updated_at": now_iso()},
             "$setOnInsert": {"id": new_id(), "status": "PENDING", "created_at": now_iso()}},
            upsert=True,
        )
    current = await db.users.find_one({"id": user["id"]}, {"_id": 0, "password_hash": 0})
    return await me(current)


@router.post("/auth/me/identity-documents")
async def add_identity_document(payload: IdentityDocumentIn, user: dict = Depends(get_current_user)):
    if account_category(user) != "PROPERTY_ADVERTISER":
        raise HTTPException(403, "Identity verification is available to Property Advertisers")
    document = {
        "id": new_id(), "user_id": user["id"], "document_type": payload.document_type,
        "file_name": payload.file_name, "url": payload.url, "status": "PENDING",
        "created_at": now_iso(), "updated_at": now_iso(),
    }
    await db.identity_documents.insert_one(document.copy())
    return document


@router.get("/users")
async def list_users(user: dict = Depends(require_staff)):
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(500)
    for item in users:
        if account_category(item) == "PROPERTY_ADVERTISER":
            profile = await db.advertiser_profiles.find_one({"user_id": item["id"]}, {"_id": 0}) or {}
            item["advertiser_relationship_type"] = profile.get("relationship_type")
            item["advertiser_profile_status"] = profile.get("status")
            item["identity_documents"] = await db.identity_documents.find(
                {"user_id": item["id"]},
                {"_id": 0, "id": 1, "document_type": 1, "status": 1, "url": 1},
            ).sort("created_at", -1).to_list(20)
    return users


@router.post("/users")
async def create_user(payload: UserCreate, user: dict = Depends(require_roles("system_admin"))):
    email = payload.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Email already registered")
    _validate_account_role(payload.account_category, payload.role)
    _validate_advertiser_relationship(payload.account_category, payload.advertiser_relationship_type)
    u = {"id": new_id(), "email": email, "name": payload.name, "role": payload.role,
         "account_category": payload.account_category, "status": payload.status,
         "phone": payload.phone, "password_hash": hash_password(payload.password),
         "created_at": now_iso()}
    await db.users.insert_one(u)
    if payload.account_category == "PROPERTY_ADVERTISER":
        await db.advertiser_profiles.insert_one({
            "id": new_id(), "user_id": u["id"],
            "relationship_type": payload.advertiser_relationship_type,
            "status": "PENDING", "created_at": now_iso(), "updated_at": now_iso(),
        })
    elif payload.account_category == "REFERRAL_PARTNER":
        await db.referral_partner_profiles.insert_one({
            "id": new_id(), "user_id": u["id"], "status": "ACTIVE",
            "created_at": now_iso(), "updated_at": now_iso(),
        })
    u.pop("password_hash", None); u.pop("_id", None)
    u["advertiser_relationship_type"] = payload.advertiser_relationship_type
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
    existing = await db.users.find_one({"id": uid}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "User not found")
    category = updates.get("account_category", account_category(existing))
    existing_profile = await db.advertiser_profiles.find_one({"user_id": uid}, {"_id": 0}) or {}
    relationship = updates.pop(
        "advertiser_relationship_type",
        existing_profile.get("relationship_type"),
    )
    _validate_account_role(
        category,
        updates.get("role", existing["role"]),
    )
    _validate_advertiser_relationship(category, relationship)
    if updates:
        await db.users.update_one({"id": uid}, {"$set": updates})
    if category == "PROPERTY_ADVERTISER":
        await db.advertiser_profiles.update_one(
            {"user_id": uid},
            {"$set": {"relationship_type": relationship, "updated_at": now_iso()},
             "$setOnInsert": {"id": new_id(), "status": "PENDING", "created_at": now_iso()}},
            upsert=True,
        )
    output = await db.users.find_one({"id": uid}, {"_id": 0, "password_hash": 0})
    if category == "PROPERTY_ADVERTISER":
        output["advertiser_relationship_type"] = relationship
    return output


@router.put("/users/{uid}/advertiser-profile/status")
async def review_advertiser_profile(
    uid: str,
    status: str,
    user: dict = Depends(require_roles("system_admin")),
):
    status = status.strip().upper()
    if status not in {"VERIFIED", "REJECTED", "PENDING"}:
        raise HTTPException(400, "Invalid advertiser profile status")
    result = await db.advertiser_profiles.update_one(
        {"user_id": uid},
        {"$set": {"status": status, "reviewed_by": user["id"], "updated_at": now_iso()}},
    )
    if not result.matched_count:
        raise HTTPException(404, "Advertiser profile not found")
    return {"ok": True, "status": status}


@router.put("/users/{uid}/password")
async def reset_user_password(uid: str, payload: PasswordUpdate,
                              user: dict = Depends(require_roles("system_admin"))):
    if len(payload.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    await db.users.update_one({"id": uid}, {"$set": {"password_hash": hash_password(payload.password)}})
    return {"ok": True}
