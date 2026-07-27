"""Content + Page-content + Notifications."""
from fastapi import APIRouter, Depends, HTTPException

from core.db import db, now_iso
from core.security import get_current_user
from seed_data import DEFAULT_PAGE_CONTENT, PAGE_SLUGS

router = APIRouter()


@router.get("/notifications")
async def list_notifications(user: dict = Depends(get_current_user)):
    return await db.notifications.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)


@router.get("/content/{key}")
async def get_content(key: str):
    doc = await db.content.find_one({"key": key}, {"_id": 0})
    return doc or {"key": key, "value": {}}


@router.put("/content/{key}")
async def set_content(key: str, payload: dict, user: dict = Depends(get_current_user)):
    await db.content.update_one({"key": key},
                                {"$set": {"key": key, "value": payload}}, upsert=True)
    return {"ok": True}


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base or {})
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


@router.get("/page/{page}")
async def get_page_content(page: str):
    if page not in PAGE_SLUGS:
        raise HTTPException(404, f"Unknown page '{page}'")
    doc = await db.page_content.find_one({"page": page}, {"_id": 0}) or {}
    stored = doc.get("sections", {})
    defaults = DEFAULT_PAGE_CONTENT.get(page, {})
    return {"page": page, "sections": _deep_merge(defaults, stored)}


@router.put("/page/{page}")
async def set_page_content(page: str, payload: dict, user: dict = Depends(get_current_user)):
    if page not in PAGE_SLUGS:
        raise HTTPException(404, f"Unknown page '{page}'")
    sections = payload.get("sections") if isinstance(payload, dict) and "sections" in payload else payload
    if not isinstance(sections, dict):
        raise HTTPException(400, "sections must be an object")
    await db.page_content.update_one(
        {"page": page},
        {"$set": {"page": page, "sections": sections,
                  "updated_at": now_iso(), "updated_by": user.get("id")}},
        upsert=True,
    )
    return {"ok": True}


@router.post("/page/{page}/list/{section}")
async def append_page_list_item(page: str, section: str, payload: dict,
                                user: dict = Depends(get_current_user)):
    if page not in PAGE_SLUGS:
        raise HTTPException(404, f"Unknown page '{page}'")
    doc = await db.page_content.find_one({"page": page}, {"_id": 0}) or {}
    sections = _deep_merge(DEFAULT_PAGE_CONTENT.get(page, {}), doc.get("sections", {}))
    lst = sections.get(section)
    if not isinstance(lst, list):
        raise HTTPException(400, f"Section '{section}' is not a list on '{page}'")
    lst.append(payload or {})
    sections[section] = lst
    await db.page_content.update_one(
        {"page": page},
        {"$set": {"page": page, "sections": sections,
                  "updated_at": now_iso(), "updated_by": user.get("id")}},
        upsert=True,
    )
    return {"ok": True, "count": len(lst)}


@router.delete("/page/{page}/list/{section}/{index}")
async def delete_page_list_item(page: str, section: str, index: int,
                                user: dict = Depends(get_current_user)):
    if page not in PAGE_SLUGS:
        raise HTTPException(404, f"Unknown page '{page}'")
    doc = await db.page_content.find_one({"page": page}, {"_id": 0}) or {}
    sections = _deep_merge(DEFAULT_PAGE_CONTENT.get(page, {}), doc.get("sections", {}))
    lst = sections.get(section)
    if not isinstance(lst, list):
        raise HTTPException(400, f"Section '{section}' is not a list on '{page}'")
    if index < 0 or index >= len(lst):
        raise HTTPException(400, "Index out of range")
    lst.pop(index)
    sections[section] = lst
    await db.page_content.update_one(
        {"page": page},
        {"$set": {"page": page, "sections": sections,
                  "updated_at": now_iso(), "updated_by": user.get("id")}},
        upsert=True,
    )
    return {"ok": True, "count": len(lst)}
