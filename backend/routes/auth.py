"""Auth (login/logout/me/registration/password reset) + Users CRUD."""
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field

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
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: Optional[str] = Field(default=None, min_length=5, max_length=40)
    password: str = Field(min_length=8, max_length=128)
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


class AdvertiserProfileCompletionIn(BaseModel):
    phone: str = Field(min_length=5, max_length=40, pattern=r"^\+?[0-9\s-]{5,40}$")
    advertiser_relationship_type: Literal[
        "OWNER", "JOINT_OWNER", "AUTHORISED_AGENT", "AUTHORISED_REPRESENTATIVE"
    ]
    terms_accepted: bool


class EmailVerificationCodeIn(BaseModel):
    code: str = Field(min_length=6, max_length=6, pattern=r"^[0-9]{6}$")


class PendingEmailChangeIn(BaseModel):
    email: EmailStr


class SelfProfileUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    phone: Optional[str] = Field(default=None, min_length=5, max_length=40)
    preferred_communication: Optional[Literal["WhatsApp", "Email", "Both"]] = None
    residential_address: Optional[str] = Field(default=None, max_length=300)
    business_name: Optional[str] = Field(default=None, max_length=160)
    ipa_registration_number: Optional[str] = Field(default=None, max_length=80)
    position: Optional[str] = Field(default=None, max_length=120)
    business_phone: Optional[str] = Field(default=None, max_length=40, pattern=r"^$|^\\+?[0-9\\s-]{5,40}$")
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
    if category not in allowed:
        raise HTTPException(400, f"Account category '{category}' is not active in this phase")
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
        "workspace_path": workspace_path(user),
        "profile_complete": user.get("profile_complete", True),
        "email_verified": user.get("email_verified", True), "token": token,
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
            "workspace_path": workspace_path(user),
            "profile_complete": user.get("profile_complete", True),
            "email_verified": user.get("email_verified", True), "token": token}


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
                "email_verified": True,
                "google_linked_at": now_iso(),
            }},
        )
        user["email_verified"] = True
        return _google_session(user, response)

    if payload.mode != "register":
        raise HTTPException(404, "No TRELPNG account was found. Use Create Account first.")
    user = {
        "id": new_id(), "email": email,
        "name": (identity.get("name") or email.split("@")[0]).strip(),
        "phone": "",
        "role": "property_advertiser", "account_category": "PROPERTY_ADVERTISER",
        "status": "ACTIVE", "auth_provider": "google", "google_sub": google_sub,
        "google_email_verified": True, "email_verified": True,
        "profile_complete": False, "created_at": now_iso(),
    }
    await db.users.insert_one(user)
    await db.advertiser_profiles.insert_one({
        "id": new_id(), "user_id": user["id"], "display_name": user["name"],
        "relationship_type": None, "terms_accepted": False,
        "status": "INCOMPLETE", "created_at": now_iso(), "updated_at": now_iso(),
    })
    session = _google_session(user, response)
    session.update({"ok": True, "login_path": "/add-property?auth=login"})
    return session


@router.post("/auth/register", status_code=201)
async def public_register(payload: PublicRegisterIn, request: Request, response: Response):
    """Public self-registration always creates a Property Advertiser."""
    fwd = request.headers.get("x-forwarded-for", "")
    ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else None)
    if not await verify_turnstile(payload.turnstile_token, ip):
        raise HTTPException(400, "Human verification failed. Please retry the check.")
    email = payload.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Email already registered")
    user = {
        "id": new_id(), "email": email, "name": payload.name.strip(), "phone": "",
        "role": "property_advertiser", "account_category": "PROPERTY_ADVERTISER", "status": "ACTIVE",
        "password_hash": hash_password(payload.password), "email_verified": False,
        "profile_complete": False, "created_at": now_iso(),
    }
    await db.users.insert_one(user)
    await db.advertiser_profiles.insert_one({
        "id": new_id(), "user_id": user["id"], "display_name": user["name"],
        "relationship_type": None, "terms_accepted": False,
        "status": "INCOMPLETE", "created_at": now_iso(), "updated_at": now_iso(),
    })
    await _issue_email_verification(user, request)
    session = _google_session(user, response)
    session.update({"ok": True, "login_path": "/add-property?auth=login"})
    return session


async def _send_verification_email(email: str, verify_url: str, code: str) -> None:
    subject = "Verify your TRELPNG email address"
    body = f"Verify your email within 24 hours: {verify_url} or enter this one-time code: {code}"
    await notify(subject, body, email)
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        return
    sender = os.environ.get("RESEND_FROM_EMAIL", "TRELPNG <noreply@trelpng.com>")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            result = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"from": sender, "to": [email], "subject": subject, "html": (
                    "<p>Confirm that this is your TRELPNG email address.</p>"
                    f'<p><a href="{verify_url}">Verify My Email Address</a></p>'
                    f"<p>Alternatively, enter this one-time code: <strong>{code}</strong></p>"
                    "<p>The link and code expire in 24 hours and can be used only once.</p>"
                )},
            )
            result.raise_for_status()
    except Exception:
        return


async def _issue_email_verification(user: dict, request: Request) -> None:
    raw_token = secrets.token_urlsafe(32)
    code = f"{secrets.randbelow(1_000_000):06d}"
    await db.email_verification_tokens.delete_many({"user_id": user["id"]})
    await db.email_verification_tokens.insert_one({
        "id": new_id(), "user_id": user["id"],
        "token_hash": hashlib.sha256(raw_token.encode()).hexdigest(),
        "code_hash": hashlib.sha256(code.encode()).hexdigest(),
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=24),
        "created_at": now_iso(),
    })
    public_url = os.environ.get("PUBLIC_APP_URL") or str(request.base_url).rstrip("/")
    await _send_verification_email(
        user["email"], f"{public_url}/add-property?auth=verify&token={raw_token}", code,
    )


async def _complete_email_verification(record: dict, response: Response) -> dict:
    user = await db.users.find_one({"id": record["user_id"]})
    if not user:
        raise HTTPException(400, "This verification request is invalid.")
    await db.users.update_one({"id": user["id"]}, {"$set": {"email_verified": True, "updated_at": now_iso()}})
    await db.email_verification_tokens.delete_many({"user_id": user["id"]})
    user["email_verified"] = True
    return _google_session(user, response)


@router.post("/auth/verify-email-token")
async def verify_email_token(payload: dict, response: Response):
    raw_token = str(payload.get("token") or "")
    record = await db.email_verification_tokens.find_one({
        "token_hash": hashlib.sha256(raw_token.encode()).hexdigest(),
        "expires_at": {"$gt": datetime.now(timezone.utc)},
    })
    if not record:
        raise HTTPException(400, "This email-verification link is invalid or has expired.")
    return await _complete_email_verification(record, response)


@router.post("/auth/verify-email-code")
async def verify_email_code(payload: EmailVerificationCodeIn, response: Response,
                            user: dict = Depends(get_current_user)):
    record = await db.email_verification_tokens.find_one({
        "user_id": user["id"], "code_hash": hashlib.sha256(payload.code.encode()).hexdigest(),
        "expires_at": {"$gt": datetime.now(timezone.utc)},
    })
    if not record:
        raise HTTPException(400, "The verification code is invalid or has expired.")
    return await _complete_email_verification(record, response)


@router.post("/auth/resend-email-verification")
async def resend_email_verification(request: Request, user: dict = Depends(get_current_user)):
    if user.get("email_verified", True):
        return {"ok": True, "message": "Your email address is already verified."}
    existing = await db.email_verification_tokens.find_one({"user_id": user["id"]})
    if existing and existing.get("created_at"):
        created = datetime.fromisoformat(existing["created_at"].replace("Z", "+00:00"))
        if datetime.now(timezone.utc) - created < timedelta(seconds=60):
            raise HTTPException(429, "Please wait one minute before requesting another email.")
    await _issue_email_verification(user, request)
    return {"ok": True, "message": "A new verification email has been sent."}


@router.put("/auth/pending-email")
async def change_pending_email(payload: PendingEmailChangeIn, request: Request,
                               user: dict = Depends(get_current_user)):
    if user.get("email_verified", True):
        raise HTTPException(400, "This email address is already verified.")
    email = payload.email.lower().strip()
    if await db.users.find_one({"email": email, "id": {"$ne": user["id"]}}):
        raise HTTPException(400, "Email already registered")
    await db.users.update_one({"id": user["id"]}, {"$set": {"email": email, "updated_at": now_iso()}})
    user["email"] = email
    await _issue_email_verification(user, request)
    return {"ok": True, "email": email, "message": "Email updated. A new verification email has been sent."}


@router.put("/auth/complete-advertiser-profile")
async def complete_advertiser_profile(payload: AdvertiserProfileCompletionIn,
                                      user: dict = Depends(get_current_user)):
    if account_category(user) != "PROPERTY_ADVERTISER":
        raise HTTPException(403, "Property Advertiser account required")
    if not user.get("email_verified", True):
        raise HTTPException(403, "Verify your email address before completing your advertiser account")
    if not payload.terms_accepted:
        raise HTTPException(400, "Accept the Terms of Use and Privacy Policy")
    _validate_advertiser_relationship("PROPERTY_ADVERTISER", payload.advertiser_relationship_type)
    timestamp = now_iso()
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"phone": payload.phone.strip(), "profile_complete": True, "updated_at": timestamp}},
    )
    await db.advertiser_profiles.update_one(
        {"user_id": user["id"]},
        {"$set": {"relationship_type": payload.advertiser_relationship_type,
                  "terms_accepted": True, "status": "PENDING", "updated_at": timestamp},
         "$setOnInsert": {"id": new_id(), "created_at": timestamp}},
        upsert=True,
    )
    return {"ok": True, "profile_complete": True}


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
    output["profile_complete"] = user.get("profile_complete", True)
    output["email_verified"] = user.get("email_verified", True)
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
    if "name" in values:
        values["name"] = " ".join(values["name"].split())
        if len(values["name"]) < 2:
            raise HTTPException(400, "Full name is required")
    user_updates = {key: values.pop(key) for key in ("name", "phone") if key in values}
    if user_updates:
        await db.users.update_one({"id": user["id"]}, {"$set": user_updates})
        if "name" in user_updates and account_category(user) == "PROPERTY_ADVERTISER":
            await db.advertiser_profiles.update_one(
                {"user_id": user["id"]}, {"$set": {"display_name": user_updates["name"], "updated_at": now_iso()}}
            )
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
    _validate_account_role("STAFF", payload.role)
    u = {"id": new_id(), "email": email, "name": payload.name, "role": payload.role,
         "account_category": "STAFF", "status": payload.status,
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
    existing = await db.users.find_one({"id": uid}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "User not found")
    if "account_category" in updates and updates["account_category"] != account_category(existing):
        raise HTTPException(400, "Account category cannot be changed after account creation")
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
