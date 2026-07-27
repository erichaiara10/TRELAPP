"""Auth (login/logout/me) + Users CRUD."""
from fastapi import APIRouter, Depends, HTTPException, Response

from core.db import db, new_id, now_iso
from core.security import (
    create_access_token, get_current_user, hash_password,
    require_roles, verify_password,
)
from models import LoginIn, PasswordUpdate, UserCreate, UserUpdate

router = APIRouter()


@router.post("/auth/login")
async def login(payload: LoginIn, response: Response):
    email = payload.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(payload.password, user.get("password_hash", "")):
        raise HTTPException(401, "Invalid email or password")
    token = create_access_token(user["id"], user["email"], user["role"])
    response.set_cookie("access_token", token, httponly=True, secure=False,
                        samesite="lax", max_age=43200, path="/")
    return {"id": user["id"], "email": user["email"], "name": user["name"],
            "role": user["role"], "token": token}


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
