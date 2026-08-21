"""Auth (login/logout/me/registration) + Users CRUD."""
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field

from core.account_policy import account_category, require_staff, workspace_path
from core.db import db, new_id, now_iso
from core.login_guard import is_locked, record_failure, reset as reset_login_failures
from core.security import (
    create_access_token, get_current_user, hash_password,
    require_roles, verify_password,
)
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


@router.post("/auth/login")
async def login(payload: LoginIn, request: Request, response: Response):
    email = payload.email.lower().strip()
    # Behind the k8s ingress, request.client.host is the proxy pod. Prefer the
    # left-most entry in X-Forwarded-For so per-IP counters actually track the
    # real caller. The email-wide counter in login_guard is the belt-and-braces.
    fwd = request.headers.get("x-forwarded-for", "")
    ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else None)
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


@router.post("/auth/register", status_code=201)
async def public_register(payload: PublicRegisterIn):
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


@router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return {**user, "account_category": account_category(user), "workspace_path": workspace_path(user)}


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
