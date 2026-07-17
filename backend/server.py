from dotenv import load_dotenv
from pathlib import Path
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import uuid
import logging
import bcrypt
import jwt
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Literal

from fastapi import FastAPI, APIRouter, Request, Response, HTTPException, Depends, UploadFile, File, Query, Header
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr
import requests

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALG = os.environ.get("JWT_ALGORITHM", "HS256")

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

app = FastAPI(title="TREL API")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("trel")

def now_iso() -> str: return datetime.now(timezone.utc).isoformat()
def new_id() -> str: return str(uuid.uuid4())
def hash_password(p: str) -> str: return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
def verify_password(p: str, h: str) -> bool:
    try: return bcrypt.checkpw(p.encode(), h.encode())
    except Exception: return False

def create_access_token(user_id: str, email: str, role: str) -> str:
    payload = {"sub": user_id, "email": email, "role": role,
               "exp": datetime.now(timezone.utc) + timedelta(hours=12), "type": "access"}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "): token = auth[7:]
    if not token: raise HTTPException(status_code=401, detail="Not authenticated")
    try: payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.ExpiredSignatureError: raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError: raise HTTPException(401, "Invalid token")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not user: raise HTTPException(401, "User not found")
    return user

def require_roles(*roles: str):
    async def _dep(user: dict = Depends(get_current_user)):
        if user["role"] != "system_admin" and user["role"] not in roles:
            raise HTTPException(403, "Forbidden")
        return user
    return _dep

def strip_id(doc):
    if doc: doc.pop("_id", None)
    return doc

# ---- Models ----
class LoginIn(BaseModel):
    email: EmailStr
    password: str

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: str
    phone: Optional[str] = None

class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    phone: Optional[str] = None

class PasswordUpdate(BaseModel):
    password: str

class Communication(BaseModel):
    id: str = Field(default_factory=new_id)
    lead_id: str
    kind: Literal["call","email","whatsapp","note","meeting","sms"] = "note"
    direction: Literal["inbound","outbound","internal"] = "outbound"
    subject: Optional[str] = ""
    body: str
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    created_at: str = Field(default_factory=now_iso)

class CommunicationCreate(BaseModel):
    kind: str = "note"
    direction: str = "outbound"
    subject: Optional[str] = ""
    body: str

class Property(BaseModel):
    id: str = Field(default_factory=new_id)
    title: str
    listing_type: Literal["sale","rent"]
    property_type: str
    price: float
    currency: str = "PGK"
    bedrooms: Optional[int] = 0
    bathrooms: Optional[int] = 0
    parking: Optional[int] = 0
    area_sqm: Optional[float] = None
    location: str
    suburb: Optional[str] = None
    address: Optional[str] = None
    map_coords: Optional[str] = None
    description: str = ""
    features: List[str] = []
    images: List[str] = []
    status: str = "active"
    featured: bool = False
    verified: bool = False
    owner_customer_id: Optional[str] = None
    assigned_agent_id: Optional[str] = None
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)

class PropertyCreate(BaseModel):
    title: str
    listing_type: str
    property_type: str
    price: float
    currency: str = "PGK"
    bedrooms: Optional[int] = 0
    bathrooms: Optional[int] = 0
    parking: Optional[int] = 0
    area_sqm: Optional[float] = None
    location: str
    suburb: Optional[str] = None
    address: Optional[str] = None
    map_coords: Optional[str] = None
    description: Optional[str] = ""
    features: List[str] = []
    images: List[str] = []
    status: Optional[str] = "active"
    featured: bool = False
    verified: bool = False
    owner_customer_id: Optional[str] = None
    assigned_agent_id: Optional[str] = None

class Customer(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    customer_type: str = "buyer"
    company: Optional[str] = None
    notes: Optional[str] = ""
    source: Optional[str] = "manual"
    assigned_agent_id: Optional[str] = None
    created_at: str = Field(default_factory=now_iso)

class CustomerCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    customer_type: Optional[str] = "buyer"
    company: Optional[str] = None
    notes: Optional[str] = ""
    source: Optional[str] = "manual"
    assigned_agent_id: Optional[str] = None

class Requirement(BaseModel):
    id: str = Field(default_factory=new_id)
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    intent: str = "buy"
    property_type: Optional[str] = None
    min_price: Optional[float] = 0
    max_price: Optional[float] = 0
    min_bedrooms: Optional[int] = 0
    locations: List[str] = []
    features_wanted: List[str] = []
    notes: Optional[str] = ""
    is_corporate: bool = False
    anonymous_public: bool = True
    status: str = "active"
    created_at: str = Field(default_factory=now_iso)

class RequirementCreate(BaseModel):
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    intent: Optional[str] = "buy"
    property_type: Optional[str] = None
    min_price: Optional[float] = 0
    max_price: Optional[float] = 0
    min_bedrooms: Optional[int] = 0
    locations: List[str] = []
    features_wanted: List[str] = []
    notes: Optional[str] = ""
    is_corporate: bool = False
    anonymous_public: bool = True

class Lead(BaseModel):
    id: str = Field(default_factory=new_id)
    source: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    message: Optional[str] = ""
    property_id: Optional[str] = None
    property_title: Optional[str] = None
    customer_id: Optional[str] = None
    requirement_id: Optional[str] = None
    status: str = "new"
    priority: str = "medium"
    assigned_agent_id: Optional[str] = None
    payload: dict = {}
    created_at: str = Field(default_factory=now_iso)

class LeadCreate(BaseModel):
    source: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    message: Optional[str] = ""
    property_id: Optional[str] = None
    payload: dict = {}
    verification_token: Optional[str] = None
    verification_answer: Optional[str] = None
    hp_website: Optional[str] = None

class Inspection(BaseModel):
    id: str = Field(default_factory=new_id)
    property_id: str
    property_title: Optional[str] = None
    customer_name: str
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    preferred_date: Optional[str] = None
    status: str = "requested"
    feedback: Optional[str] = ""
    assigned_agent_id: Optional[str] = None
    created_at: str = Field(default_factory=now_iso)

class InspectionCreate(BaseModel):
    property_id: str
    customer_name: str
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    preferred_date: Optional[str] = None
    feedback: Optional[str] = ""
    verification_token: Optional[str] = None
    verification_answer: Optional[str] = None
    hp_website: Optional[str] = None

class Task(BaseModel):
    id: str = Field(default_factory=new_id)
    title: str
    description: Optional[str] = ""
    category: Optional[str] = "follow_up"
    due_date: Optional[str] = None
    assigned_to: Optional[str] = None
    related_lead_id: Optional[str] = None
    related_property_id: Optional[str] = None
    related_customer_id: Optional[str] = None
    status: str = "open"
    priority: str = "medium"
    created_at: str = Field(default_factory=now_iso)

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = ""
    category: Optional[str] = "follow_up"
    due_date: Optional[str] = None
    assigned_to: Optional[str] = None
    related_lead_id: Optional[str] = None
    related_property_id: Optional[str] = None
    related_customer_id: Optional[str] = None
    priority: Optional[str] = "medium"

class Notification(BaseModel):
    id: str = Field(default_factory=new_id)
    kind: str
    to: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    read: bool = False
    created_at: str = Field(default_factory=now_iso)

# ---- Human verification (captcha) ----
import random
import string

# Exclude visually confusable characters (0/O, 1/I/l)
_CAPTCHA_ALPHABET = (
    string.ascii_uppercase.replace("O", "").replace("I", "")
    + string.digits.replace("0", "").replace("1", "")
)

def _captcha_pair():
    code = "".join(random.choices(_CAPTCHA_ALPHABET, k=5))
    return f"Type these letters/numbers: {code}", code

def _captcha_encode(answer: str) -> str:
    payload = {"a": answer, "type": "captcha",
               "exp": datetime.now(timezone.utc) + timedelta(minutes=15)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def _captcha_verify(token: Optional[str], answer: Optional[str]) -> None:
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
    # Case-insensitive comparison for alphanumeric codes
    if str(answer).strip().upper() != str(payload.get("a", "")).strip().upper():
        raise HTTPException(400, "Incorrect verification — please try again")

def _honeypot_check(hp: Optional[str]) -> None:
    if hp:
        raise HTTPException(400, "Bot detected")

@api.get("/public/challenge")
async def get_public_challenge():
    q, a = _captcha_pair()
    return {"question": q, "token": _captcha_encode(a)}

# ---- Auth ----
@api.post("/auth/login")
async def login(payload: LoginIn, response: Response):
    email = payload.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(payload.password, user.get("password_hash","")):
        raise HTTPException(401, "Invalid email or password")
    token = create_access_token(user["id"], user["email"], user["role"])
    response.set_cookie("access_token", token, httponly=True, secure=False, samesite="lax", max_age=43200, path="/")
    return {"id": user["id"], "email": user["email"], "name": user["name"], "role": user["role"], "token": token}

@api.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}

@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)): return user

# ---- Users ----
@api.get("/users")
async def list_users(user: dict = Depends(get_current_user)):
    return await db.users.find({}, {"_id":0,"password_hash":0}).to_list(500)

@api.post("/users")
async def create_user(payload: UserCreate, user: dict = Depends(require_roles("system_admin"))):
    email = payload.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Email already registered")
    u = {"id": new_id(), "email": email, "name": payload.name, "role": payload.role,
         "phone": payload.phone, "password_hash": hash_password(payload.password), "created_at": now_iso()}
    await db.users.insert_one(u)
    u.pop("password_hash", None); u.pop("_id", None)
    return u

@api.delete("/users/{uid}")
async def delete_user(uid: str, user: dict = Depends(require_roles("system_admin"))):
    if uid == user["id"]: raise HTTPException(400, "Cannot delete self")
    await db.users.delete_one({"id": uid})
    return {"ok": True}

@api.put("/users/{uid}")
async def update_user(uid: str, payload: UserUpdate, user: dict = Depends(require_roles("system_admin"))):
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if "email" in updates:
        email = updates["email"].lower().strip()
        clash = await db.users.find_one({"email": email, "id": {"$ne": uid}})
        if clash: raise HTTPException(400, "Email already in use")
        updates["email"] = email
    if not updates:
        raise HTTPException(400, "No changes provided")
    await db.users.update_one({"id": uid}, {"$set": updates})
    return await db.users.find_one({"id": uid}, {"_id":0, "password_hash":0})

@api.put("/users/{uid}/password")
async def reset_user_password(uid: str, payload: PasswordUpdate, user: dict = Depends(require_roles("system_admin"))):
    if len(payload.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    await db.users.update_one({"id": uid}, {"$set": {"password_hash": hash_password(payload.password)}})
    return {"ok": True}

# ---- Properties ----
def _q_match(field, value):
    return {field: value} if value else {}

def _q_gte(field, value):
    return {field: {"$gte": value}} if value is not None else {}

def _q_price(min_price, max_price):
    if min_price is None and max_price is None: return {}
    pr = {}
    if min_price is not None: pr["$gte"] = min_price
    if max_price is not None: pr["$lte"] = max_price
    return {"price": pr}

def _q_search(q):
    if not q: return {}
    return {"$or": [{f: {"$regex": q, "$options": "i"}} for f in ("title","description","suburb","location")]}

def _q_bool(field, value):
    return {field: value} if value is not None else {}

def _build_property_query(filters: dict) -> dict:
    query = {}
    for part in (
        _q_match("listing_type", filters.get("listing_type")),
        _q_match("property_type", filters.get("property_type")),
        _q_match("location", filters.get("location")),
        _q_match("status", filters.get("status")),
        _q_gte("bedrooms", filters.get("bedrooms")),
        _q_bool("featured", filters.get("featured")),
        _q_price(filters.get("min_price"), filters.get("max_price")),
        _q_search(filters.get("q")),
    ):
        query.update(part)
    return query

class PropertyFilters(BaseModel):
    listing_type: Optional[str] = None
    property_type: Optional[str] = None
    location: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    bedrooms: Optional[int] = None
    featured: Optional[bool] = None
    status: Optional[str] = "active"
    q: Optional[str] = None
    limit: int = 60

@api.get("/properties")
async def list_properties(filters: PropertyFilters = Depends()):
    query = _build_property_query(filters.model_dump(exclude={"limit"}))
    return await db.properties.find(query, {"_id": 0}).sort("created_at", -1).to_list(filters.limit)

@api.get("/properties/{pid}")
async def get_property(pid: str):
    doc = await db.properties.find_one({"id": pid}, {"_id":0})
    if not doc: raise HTTPException(404, "Property not found")
    return doc

@api.post("/properties")
async def create_property(payload: PropertyCreate, user: dict = Depends(get_current_user)):
    p = Property(**payload.model_dump()).model_dump()
    await db.properties.insert_one(p)
    return strip_id(p)

@api.put("/properties/{pid}")
async def update_property(pid: str, payload: dict, user: dict = Depends(get_current_user)):
    payload["updated_at"] = now_iso()
    payload.pop("id",None); payload.pop("_id",None)
    await db.properties.update_one({"id": pid}, {"$set": payload})
    return await db.properties.find_one({"id": pid}, {"_id":0})

@api.delete("/properties/{pid}")
async def delete_property(pid: str, user: dict = Depends(get_current_user)):
    await db.properties.delete_one({"id": pid})
    return {"ok": True}

# ---- Customers ----
@api.get("/customers")
async def list_customers(user: dict = Depends(get_current_user)):
    return await db.customers.find({}, {"_id":0}).sort("created_at",-1).to_list(1000)

@api.post("/customers")
async def create_customer(payload: CustomerCreate, user: dict = Depends(get_current_user)):
    c = Customer(**payload.model_dump()).model_dump()
    await db.customers.insert_one(c)
    return strip_id(c)

@api.put("/customers/{cid}")
async def update_customer(cid: str, payload: dict, user: dict = Depends(get_current_user)):
    payload.pop("id",None); payload.pop("_id",None)
    await db.customers.update_one({"id": cid}, {"$set": payload})
    return await db.customers.find_one({"id": cid}, {"_id":0})

@api.delete("/customers/{cid}")
async def delete_customer(cid: str, user: dict = Depends(get_current_user)):
    await db.customers.delete_one({"id": cid})
    return {"ok": True}

# ---- Requirements ----
@api.get("/requirements")
async def list_requirements(user: dict = Depends(get_current_user)):
    return await db.requirements.find({}, {"_id":0}).sort("created_at",-1).to_list(1000)

@api.get("/requirements/public")
async def public_requirements():
    return await db.requirements.find(
        {"anonymous_public": True, "status": "active"},
        {"_id":0, "customer_id":0, "customer_name":0}
    ).sort("created_at",-1).to_list(50)

@api.post("/requirements")
async def create_requirement(payload: RequirementCreate, user: dict = Depends(get_current_user)):
    r = Requirement(**payload.model_dump()).model_dump()
    await db.requirements.insert_one(r)
    return strip_id(r)

@api.delete("/requirements/{rid}")
async def delete_requirement(rid: str, user: dict = Depends(get_current_user)):
    await db.requirements.delete_one({"id": rid})
    return {"ok": True}

# ---- Leads ----
@api.get("/leads")
async def list_leads(user: dict = Depends(get_current_user)):
    return await db.leads.find({}, {"_id":0}).sort("created_at",-1).to_list(2000)

@api.put("/leads/{lid}")
async def update_lead(lid: str, payload: dict, user: dict = Depends(get_current_user)):
    payload.pop("id",None); payload.pop("_id",None)
    await db.leads.update_one({"id": lid}, {"$set": payload})
    return await db.leads.find_one({"id": lid}, {"_id":0})

@api.delete("/leads/{lid}")
async def delete_lead(lid: str, user: dict = Depends(get_current_user)):
    await db.leads.delete_one({"id": lid})
    await db.communications.delete_many({"lead_id": lid})
    return {"ok": True}

# ---- Communications history ----
@api.get("/leads/{lid}/communications")
async def list_lead_communications(lid: str, user: dict = Depends(get_current_user)):
    return await db.communications.find({"lead_id": lid}, {"_id":0}).sort("created_at", 1).to_list(500)

@api.post("/leads/{lid}/communications")
async def create_lead_communication(lid: str, payload: CommunicationCreate, user: dict = Depends(get_current_user)):
    lead = await db.leads.find_one({"id": lid}, {"_id":0, "id":1})
    if not lead: raise HTTPException(404, "Lead not found")
    body = payload.body.strip()
    if not body: raise HTTPException(400, "Body is required")
    c = Communication(
        lead_id=lid, kind=payload.kind, direction=payload.direction,
        subject=payload.subject, body=body,
        agent_id=user["id"], agent_name=user["name"],
    ).model_dump()
    await db.communications.insert_one(c)
    strip_id(c)
    return c

@api.delete("/communications/{cid}")
async def delete_communication(cid: str, user: dict = Depends(get_current_user)):
    await db.communications.delete_one({"id": cid})
    return {"ok": True}

# ---- Public leads ----
async def _auto_assign_agent(prefer_role: str = "sales_agent") -> Optional[str]:
    agent = await db.users.find_one({"role": prefer_role}, {"_id":0, "id":1})
    return agent["id"] if agent else None

async def _notify(subject: str, body: str, to: Optional[str] = None):
    n = Notification(kind="email_sim", to=to, subject=subject, body=body).model_dump()
    await db.notifications.insert_one(n)

@api.post("/public/leads")
async def public_create_lead(payload: LeadCreate):
    _honeypot_check(payload.hp_website)
    _captcha_verify(payload.verification_token, payload.verification_answer)
    p = payload.model_dump()
    prop_title = None
    if p.get("property_id"):
        prop = await db.properties.find_one({"id": p["property_id"]}, {"_id":0, "title":1})
        if prop: prop_title = prop["title"]
    role = "leasing_agent" if p["source"] == "management_form" else "sales_agent"
    lead = Lead(source=p["source"], name=p["name"], email=p.get("email"), phone=p.get("phone"),
        message=p.get("message",""), property_id=p.get("property_id"), property_title=prop_title,
        payload=p.get("payload",{}), assigned_agent_id=await _auto_assign_agent(role)).model_dump()
    await db.leads.insert_one(lead)
    if payload.name:
        ctype = {"sell_form":"seller","wanted_form":"buyer","corporate_form":"corporate",
                 "management_form":"landlord","inspection_form":"buyer","contact_form":"buyer"}.get(p["source"],"buyer")
        cust = Customer(name=payload.name, email=payload.email, phone=payload.phone,
                        customer_type=ctype, source=p["source"], assigned_agent_id=lead["assigned_agent_id"]).model_dump()
        await db.customers.insert_one(cust)
        await db.leads.update_one({"id": lead["id"]}, {"$set": {"customer_id": cust["id"]}})
    if p["source"] in ("wanted_form","corporate_form"):
        pd = p.get("payload",{})
        req = Requirement(customer_name=payload.name, intent=pd.get("intent","buy"),
            property_type=pd.get("property_type"), min_price=pd.get("min_price",0),
            max_price=pd.get("max_price",0), min_bedrooms=pd.get("min_bedrooms",0),
            locations=pd.get("locations",[]), notes=payload.message or "",
            is_corporate=(p["source"]=="corporate_form")).model_dump()
        await db.requirements.insert_one(req)
        await db.leads.update_one({"id": lead["id"]}, {"$set": {"requirement_id": req["id"]}})
    await _notify(f"New {p['source']} enquiry from {payload.name}", payload.message or "See lead in dashboard", payload.email)
    return {"ok": True, "lead_id": lead["id"]}

@api.post("/public/inspections")
async def public_create_inspection(payload: InspectionCreate):
    _honeypot_check(payload.hp_website)
    _captcha_verify(payload.verification_token, payload.verification_answer)
    prop = await db.properties.find_one({"id": payload.property_id}, {"_id":0, "title":1})
    if not prop: raise HTTPException(404, "Property not found")
    ins = Inspection(property_id=payload.property_id, property_title=prop["title"],
        customer_name=payload.customer_name, customer_phone=payload.customer_phone,
        customer_email=payload.customer_email, preferred_date=payload.preferred_date,
        assigned_agent_id=await _auto_assign_agent("sales_agent")).model_dump()
    await db.inspections.insert_one(ins)
    lead = Lead(source="inspection_form", name=payload.customer_name, email=payload.customer_email,
        phone=payload.customer_phone, property_id=payload.property_id, property_title=prop["title"],
        payload={"preferred_date": payload.preferred_date}, assigned_agent_id=ins["assigned_agent_id"]).model_dump()
    await db.leads.insert_one(lead)
    await _notify(f"New inspection request: {prop['title']}", payload.customer_name, payload.customer_email)
    return {"ok": True, "inspection_id": ins["id"]}

# ---- Inspections (staff) ----
@api.get("/inspections")
async def list_inspections(user: dict = Depends(get_current_user)):
    return await db.inspections.find({}, {"_id":0}).sort("created_at",-1).to_list(1000)

@api.put("/inspections/{iid}")
async def update_inspection(iid: str, payload: dict, user: dict = Depends(get_current_user)):
    payload.pop("id",None); payload.pop("_id",None)
    await db.inspections.update_one({"id": iid}, {"$set": payload})
    return await db.inspections.find_one({"id": iid}, {"_id":0})

# ---- Tasks ----
@api.get("/tasks")
async def list_tasks(user: dict = Depends(get_current_user)):
    return await db.tasks.find({}, {"_id":0}).sort("created_at",-1).to_list(1000)

@api.post("/tasks")
async def create_task(payload: TaskCreate, user: dict = Depends(get_current_user)):
    t = Task(**payload.model_dump()).model_dump()
    await db.tasks.insert_one(t)
    return strip_id(t)

@api.put("/tasks/{tid}")
async def update_task(tid: str, payload: dict, user: dict = Depends(get_current_user)):
    payload.pop("id",None); payload.pop("_id",None)
    await db.tasks.update_one({"id": tid}, {"$set": payload})
    return await db.tasks.find_one({"id": tid}, {"_id":0})

@api.delete("/tasks/{tid}")
async def delete_task(tid: str, user: dict = Depends(get_current_user)):
    await db.tasks.delete_one({"id": tid})
    return {"ok": True}

# ---- Matching ----
def _score_intent(req: dict, prop: dict) -> int:
    intent, ltype = req.get("intent"), prop.get("listing_type")
    if intent == "buy" and ltype == "sale": return 20
    if intent == "rent" and ltype == "rent": return 20
    if intent == "either": return 10
    return 0

def _score_type(req: dict, prop: dict) -> int:
    if req.get("property_type") and req["property_type"] == prop.get("property_type"): return 20
    return 0

def _score_price(req: dict, prop: dict) -> int:
    price = prop.get("price", 0)
    lo, hi = req.get("min_price") or 0, req.get("max_price") or 0
    s = 0
    if hi and price <= hi: s += 15
    if not hi: s += 5
    if lo and price >= lo: s += 5
    return s

def _score_bedrooms(req: dict, prop: dict) -> int:
    if (prop.get("bedrooms") or 0) >= (req.get("min_bedrooms") or 0): return 15
    return 0

def _score_location(req: dict, prop: dict) -> int:
    locs = req.get("locations") or []
    if not locs or prop.get("location") in locs or prop.get("suburb") in locs: return 15
    return 0

def score_match(req: dict, prop: dict) -> int:
    if prop.get("status") != "active":
        return 0
    total = _score_intent(req, prop) + _score_type(req, prop) + _score_price(req, prop) \
        + _score_bedrooms(req, prop) + _score_location(req, prop)
    return max(0, total)

@api.get("/matching/{requirement_id}")
async def match_requirement(requirement_id: str, user: dict = Depends(get_current_user)):
    req = await db.requirements.find_one({"id": requirement_id}, {"_id":0})
    if not req: raise HTTPException(404, "Requirement not found")
    props = await db.properties.find({"status":"active"}, {"_id":0}).to_list(500)
    scored = [{"property": p, "score": score_match(req, p)} for p in props]
    scored.sort(key=lambda x: x["score"], reverse=True)
    return {"requirement": req, "matches": scored[:20]}

# ---- Notifications / Content ----
@api.get("/notifications")
async def list_notifications(user: dict = Depends(get_current_user)):
    return await db.notifications.find({}, {"_id":0}).sort("created_at",-1).to_list(200)

@api.get("/content/{key}")
async def get_content(key: str):
    doc = await db.content.find_one({"key": key}, {"_id":0})
    return doc or {"key": key, "value": {}}

@api.put("/content/{key}")
async def set_content(key: str, payload: dict, user: dict = Depends(get_current_user)):
    await db.content.update_one({"key": key}, {"$set": {"key": key, "value": payload}}, upsert=True)
    return {"ok": True}

# ---- Page Content (per-page structured content) ----
PAGE_SLUGS = {"home","about","sell","buy","rent","wanted","management","corporate","contact","legal_privacy","legal_terms"}

def _deep_merge(base: dict, override: dict) -> dict:
    """Merge override into base (dicts merged recursively; lists/scalars replaced)."""
    out = dict(base or {})
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out

@api.get("/page/{page}")
async def get_page_content(page: str):
    if page not in PAGE_SLUGS:
        raise HTTPException(404, f"Unknown page '{page}'")
    doc = await db.page_content.find_one({"page": page}, {"_id": 0}) or {}
    stored = doc.get("sections", {})
    defaults = DEFAULT_PAGE_CONTENT.get(page, {})
    return {"page": page, "sections": _deep_merge(defaults, stored)}

@api.put("/page/{page}")
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

@api.post("/page/{page}/list/{section}")
async def append_page_list_item(page: str, section: str, payload: dict, user: dict = Depends(get_current_user)):
    if page not in PAGE_SLUGS:
        raise HTTPException(404, f"Unknown page '{page}'")
    # Fetch merged current
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

@api.delete("/page/{page}/list/{section}/{index}")
async def delete_page_list_item(page: str, section: str, index: int, user: dict = Depends(get_current_user)):
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


# ---- Reports ----
@api.get("/reports/summary")
async def reports_summary(user: dict = Depends(get_current_user)):
    async def count(coll, q=None): return await coll.count_documents(q or {})
    return {
        "properties_active": await count(db.properties, {"status":"active"}),
        "properties_sold": await count(db.properties, {"status":"sold"}),
        "properties_leased": await count(db.properties, {"status":"leased"}),
        "leads_new": await count(db.leads, {"status":"new"}),
        "leads_total": await count(db.leads),
        "customers": await count(db.customers),
        "requirements_active": await count(db.requirements, {"status":"active"}),
        "inspections_open": await count(db.inspections, {"status":{"$in":["requested","scheduled"]}}),
        "tasks_open": await count(db.tasks, {"status":{"$in":["open","in_progress"]}}),
    }

@api.get("/reports/leads_by_source")
async def leads_by_source(user: dict = Depends(get_current_user)):
    rows = await db.leads.aggregate([{"$group":{"_id":"$source","count":{"$sum":1}}}]).to_list(100)
    return [{"source": r["_id"], "count": r["count"]} for r in rows]

@api.get("/")
async def root(): return {"ok": True, "service": "TREL API"}

# ---- Object storage (Emergent) ----
STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
APP_NAME = "trel"
_storage_key = None

def _init_storage():
    global _storage_key
    if _storage_key or not EMERGENT_KEY: return _storage_key
    try:
        r = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
        r.raise_for_status()
        _storage_key = r.json()["storage_key"]
        logger.info("Storage initialised")
    except Exception as e:
        logger.warning(f"Storage init failed: {e}")
    return _storage_key

def _put_object(path: str, data: bytes, content_type: str) -> dict:
    global _storage_key
    key = _init_storage()
    if not key: raise HTTPException(503, "Storage unavailable")
    r = requests.put(f"{STORAGE_URL}/objects/{path}",
                     headers={"X-Storage-Key": key, "Content-Type": content_type},
                     data=data, timeout=120)
    if r.status_code == 403:
        _storage_key = None
        key = _init_storage()
        r = requests.put(f"{STORAGE_URL}/objects/{path}",
                         headers={"X-Storage-Key": key, "Content-Type": content_type},
                         data=data, timeout=120)
    r.raise_for_status()
    return r.json()

def _get_object(path: str):
    global _storage_key
    key = _init_storage()
    if not key: raise HTTPException(503, "Storage unavailable")
    r = requests.get(f"{STORAGE_URL}/objects/{path}",
                     headers={"X-Storage-Key": key}, timeout=60)
    if r.status_code == 403:
        _storage_key = None
        key = _init_storage()
        r = requests.get(f"{STORAGE_URL}/objects/{path}",
                         headers={"X-Storage-Key": key}, timeout=60)
    r.raise_for_status()
    return r.content, r.headers.get("Content-Type", "application/octet-stream")

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
EXT_FROM_MIME = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

@api.post("/public/upload")
async def public_upload(file: UploadFile = File(...)):
    """Public image upload — used by the Sell/Wanted forms to attach property photos."""
    ct = (file.content_type or "").lower()
    if ct not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(400, "Only JPG, PNG or WebP images are allowed")
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(400, "Image exceeds 10 MB limit")
    if len(data) < 100:
        raise HTTPException(400, "Uploaded file is empty")
    ext = EXT_FROM_MIME[ct]
    file_id = new_id()
    path = f"{APP_NAME}/uploads/public/{file_id}.{ext}"
    result = _put_object(path, data, ct)
    await db.files.insert_one({
        "id": file_id, "storage_path": result["path"],
        "original_filename": file.filename, "content_type": ct,
        "size": result.get("size", len(data)), "is_deleted": False,
        "source": "public_upload", "created_at": now_iso(),
    })
    return {"id": file_id, "url": f"/api/files/{file_id}"}

@api.get("/files/{file_id}")
async def download_file(file_id: str):
    rec = await db.files.find_one({"id": file_id, "is_deleted": False}, {"_id": 0})
    if not rec: raise HTTPException(404, "File not found")
    data, ct = _get_object(rec["storage_path"])
    return Response(content=data, media_type=rec.get("content_type") or ct,
                    headers={"Cache-Control": "public, max-age=86400"})


# ---- Seed ----
DEMO_PROPERTIES = [
    {"title":"Modern 4BR Beachfront Villa, Ela Beach","listing_type":"sale","property_type":"house","price":1450000,"bedrooms":4,"bathrooms":3,"parking":2,"area_sqm":420,"location":"Port Moresby","suburb":"Ela Beach","address":"12 Ela Beach Road","featured":True,"verified":True,
     "description":"Elegant villa steps from Ela Beach with tropical gardens, pool, and secure compound.","features":["Pool","Secure Compound","Ocean View","Backup Generator"],
     "images":["https://images.pexels.com/photos/1974596/pexels-photo-1974596.jpeg","https://images.pexels.com/photos/12081268/pexels-photo-12081268.jpeg"]},
    {"title":"Executive Apartment, Touaguba Hill","listing_type":"rent","property_type":"apartment","price":6500,"bedrooms":3,"bathrooms":2,"parking":1,"area_sqm":180,"location":"Port Moresby","suburb":"Touaguba Hill","featured":True,"verified":True,
     "description":"Fully furnished executive apartment with panoramic harbour views, 24/7 security, and gym.","features":["Furnished","Harbour View","Gym","24/7 Security"],
     "images":["https://images.pexels.com/photos/23669334/pexels-photo-23669334.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940","https://images.unsplash.com/photo-1760067537639-0fb475c87657"]},
    {"title":"Family Home in Gordons","listing_type":"sale","property_type":"house","price":780000,"bedrooms":3,"bathrooms":2,"parking":2,"area_sqm":260,"location":"Port Moresby","suburb":"Gordons","verified":True,
     "description":"Well-maintained family home in quiet Gordons cul-de-sac. Large garden, servant quarters.","features":["Garden","Servant Quarters","Fenced"],
     "images":["https://images.pexels.com/photos/12081268/pexels-photo-12081268.jpeg"]},
    {"title":"Lae CBD Commercial Space","listing_type":"rent","property_type":"commercial","price":12000,"bedrooms":0,"bathrooms":2,"parking":6,"area_sqm":320,"location":"Lae","suburb":"CBD",
     "description":"Ground floor retail/office space in Lae CBD with high foot traffic.","features":["Ground Floor","Parking","A/C"],
     "images":["https://images.unsplash.com/photo-1760067537639-0fb475c87657"]},
    {"title":"Land 1200sqm, 9-Mile","listing_type":"sale","property_type":"land","price":220000,"bedrooms":0,"bathrooms":0,"parking":0,"area_sqm":1200,"location":"Port Moresby","suburb":"9-Mile",
     "description":"Flat block ready to build, close to Jackson's Airport. Fenced perimeter.","features":["Flat","Fenced","Titled"],
     "images":["https://images.pexels.com/photos/1974596/pexels-photo-1974596.jpeg"]},
    {"title":"Townhouse, Boroko","listing_type":"rent","property_type":"townhouse","price":4200,"bedrooms":2,"bathrooms":2,"parking":1,"area_sqm":140,"location":"Port Moresby","suburb":"Boroko","featured":True,
     "description":"Modern 2BR townhouse in gated community, close to shopping and schools.","features":["Gated Community","Pool","Pet Friendly"],
     "images":["https://images.pexels.com/photos/23669334/pexels-photo-23669334.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940"]},
]

DEMO_USERS = [
    {"email": os.environ.get("ADMIN_EMAIL","admin@trel.com.pg"), "name":"System Admin","role":"system_admin"},
    {"email":"director@trel.com.pg","name":"Naomi Kila","role":"managing_director"},
    {"email":"sales@trel.com.pg","name":"John Namaliu","role":"sales_agent"},
    {"email":"leasing@trel.com.pg","name":"Grace Toua","role":"leasing_agent"},
    {"email":"marketing@trel.com.pg","name":"Peter Amet","role":"marketing_officer"},
]

LEGACY_EMAIL_MAP = {
    "admin@pngrealty.pg": "admin@trel.com.pg",
    "director@pngrealty.pg": "director@trel.com.pg",
    "sales@pngrealty.pg": "sales@trel.com.pg",
    "leasing@pngrealty.pg": "leasing@trel.com.pg",
    "marketing@pngrealty.pg": "marketing@trel.com.pg",
}

async def _migrate_legacy_user_emails():
    for old, new in LEGACY_EMAIL_MAP.items():
        old_user = await db.users.find_one({"email": old})
        if not old_user:
            continue
        new_user = await db.users.find_one({"email": new})
        if new_user:
            # New already exists; delete old to avoid duplicates
            await db.users.delete_one({"email": old})
        else:
            await db.users.update_one({"email": old}, {"$set": {"email": new}})

DEFAULT_CONTENT = {
    "site": {"agency_name":"Triumph Real Estate Limited","short_name":"TREL",
             "tagline":"We Care To Share",
             "logo_url":"https://customer-assets.emergentagent.com/job_req-to-web-1/artifacts/uh12vkjw_TREL%20Logo.png",
             "favicon_url":"https://customer-assets.emergentagent.com/job_req-to-web-1/artifacts/uh12vkjw_TREL%20Logo.png",
             "og_image_url":"https://customer-assets.emergentagent.com/job_req-to-web-1/artifacts/uh12vkjw_TREL%20Logo.png",
             "og_description":"Triumph Real Estate Limited — verified homes, apartments, land and commercial properties across Papua New Guinea. We Care To Share.",
             "phone":"+675 76281552","whatsapp":"+675 8138 3302","email":"sales101.trel@gmail.com",
             "address":"Lot 33, Section 38, Unity Mall, Steamships Compound, Waigani Rd. P.O. Box 1061, Vision City, National Capital District, PNG"},
    "about": {"heading":"About Triumph Real Estate Limited","body":"Triumph Real Estate Limited (TREL) is a Papua New Guinea-owned real estate agency helping families, investors and corporates find the right home, tenant or asset. We combine deep local knowledge with modern, transparent processes — because we care to share."},
    "why": {"heading":"Why choose TREL","items":[
        {"title":"Local expertise","body":"Born and raised in PNG — we know every suburb, security landscape, and school catchment."},
        {"title":"Verified listings","body":"Every property is checked by our team before it goes live."},
        {"title":"Corporate ready","body":"We handle expat relocations, corporate leases and portfolio management end-to-end."},
    ]},
}

# ---- Structured, admin-editable per-page content defaults ----
DEFAULT_PAGE_CONTENT = {
    "home": {
        "hero": {
            "image": "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=1600&q=80",
            "kicker": "PAPUA NEW GUINEA REAL ESTATE",
            "heading": "Find a place you're proud to call home.",
            "sub": "Verified listings, honest advice, and end-to-end support — from families to corporates across PNG.",
            "cta_primary": {"label": "Browse homes for sale", "href": "/buy"},
            "cta_secondary": {"label": "Explore rentals", "href": "/rent"},
        },
        "featured_intro": {
            "kicker": "FEATURED",
            "heading": "Handpicked homes ready to inspect",
            "sub": "A rotating selection of our most-loved listings — refreshed weekly by our sales team.",
        },
        "why_us": {
            "heading": "Why families and corporates choose TREL",
            "items": [
                {"title": "Local expertise", "body": "Born and raised in PNG — we know every suburb, security landscape and school catchment.", "icon": "MapPin"},
                {"title": "Verified listings", "body": "Every property is inspected and photographed by our team before going live.", "icon": "ShieldCheck"},
                {"title": "Corporate ready", "body": "Expat relocation, corporate leases, and portfolio management — all handled in-house.", "icon": "Briefcase"},
            ],
        },
        "wanted_preview": {
            "kicker": "PROPERTY WANTED",
            "heading": "Buyers and tenants actively searching",
            "sub": "Have a property that might match? Submit it and we'll shortlist you within 24 hours.",
        },
        "cta_band": {
            "heading": "Ready to list, buy, or rent?",
            "sub": "Talk to a TREL agent today — we typically reply within one business day.",
            "button_label": "Get in touch",
        },
    },
    "about": {
        "hero": {
            "image": "https://images.unsplash.com/photo-1497366216548-37526070297c?auto=format&fit=crop&w=1600&q=80",
            "kicker": "ABOUT TREL",
            "heading": "A PNG-owned real estate agency built on trust.",
            "intro": "Triumph Real Estate Limited helps families, investors and corporates buy, sell, rent and manage property across Papua New Guinea.",
        },
        "story": {
            "heading": "Our story",
            "body": "TREL was founded to bring transparent, professional real estate services to Papua New Guinea. From day one we've focused on verified listings, honest pricing, and long-term relationships — with families, corporates, and government clients alike.\n\nToday we serve buyers, sellers, tenants, landlords and corporate clients across Port Moresby and beyond — combining local knowledge with modern digital tools.",
        },
        "mission": {
            "heading": "Our mission",
            "body": "To make property in Papua New Guinea accessible, transparent, and rewarding for everyone we serve — because we care to share.",
        },
        "vision": {
            "heading": "Our vision",
            "body": "To be the most trusted real estate partner in the Pacific, known for integrity, local expertise and lasting relationships.",
        },
        "values": [
            {"title": "Integrity", "body": "Straight-talking advice, honest pricing, no surprises."},
            {"title": "Local knowledge", "body": "We know PNG's suburbs, schools, and security landscape inside-out."},
            {"title": "Care", "body": "We treat every client's home like our own — because we care to share."},
        ],
        "team": [
            {"name": "Managing Director", "role": "Managing Director", "photo": "", "bio": "Leads TREL's strategy, corporate partnerships, and community programmes."},
            {"name": "Sales Manager", "role": "Head of Sales", "photo": "", "bio": "Oversees residential and commercial sales across Port Moresby."},
            {"name": "Leasing Manager", "role": "Head of Leasing", "photo": "", "bio": "Manages rentals, corporate leases and expat relocation."},
        ],
    },
    "sell": {
        "hero": {
            "image": "https://images.unsplash.com/photo-1560518883-ce09059eeffa?auto=format&fit=crop&w=1600&q=80",
            "kicker": "SELL WITH TREL",
            "heading": "List your property",
            "intro": "Tell us about your property — a TREL agent will schedule an appraisal and walk you through our marketing plan. Adding photos speeds up appraisal by 2–3 days.",
        },
        "benefits": [
            {"title": "Free appraisal", "body": "An accurate, market-based price backed by recent comparable sales."},
            {"title": "Professional photography", "body": "Every listing gets a photo shoot before going live."},
            {"title": "Verified marketing", "body": "Featured on our homepage, WhatsApp broadcasts and partner networks."},
        ],
    },
    "buy": {
        "hero": {
            "image": "https://images.unsplash.com/photo-1568605114967-8130f3a36994?auto=format&fit=crop&w=1600&q=80",
            "kicker": "BUY WITH TREL",
            "heading": "Homes and investments across Papua New Guinea",
            "intro": "Browse verified houses, apartments, land and commercial properties. Every listing is inspected by our team.",
        },
    },
    "rent": {
        "hero": {
            "image": "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?auto=format&fit=crop&w=1600&q=80",
            "kicker": "RENT WITH TREL",
            "heading": "Rentals for families, expats and corporates",
            "intro": "From compact apartments to executive housing — search verified rentals updated weekly.",
        },
    },
    "wanted": {
        "hero": {
            "image": "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?auto=format&fit=crop&w=1600&q=80",
            "kicker": "PROPERTY WANTED",
            "heading": "Tell us what you're looking for",
            "intro": "Post your requirements — our team will shortlist matching properties within 24 hours and notify you when new ones list.",
        },
    },
    "management": {
        "hero": {
            "image": "https://images.unsplash.com/photo-1497366754035-f200968a6e72?auto=format&fit=crop&w=1600&q=80",
            "kicker": "PROPERTY MANAGEMENT",
            "heading": "End-to-end management for landlords",
            "intro": "We tenant, inspect, collect rent and maintain your property — so you can focus on the return.",
        },
        "services": [
            {"title": "Tenant sourcing", "body": "Vetted tenants, reference checks, and secure lease drafting.", "icon": "Users"},
            {"title": "Rent collection", "body": "Automated invoicing, receipting, and monthly owner statements.", "icon": "Wallet"},
            {"title": "Maintenance", "body": "24/7 emergency response with trusted local trade partners.", "icon": "Wrench"},
            {"title": "Inspections", "body": "Quarterly condition reports with photos, delivered to your inbox.", "icon": "ClipboardCheck"},
        ],
    },
    "corporate": {
        "hero": {
            "image": "https://images.unsplash.com/photo-1554469384-e58fac16e23a?auto=format&fit=crop&w=1600&q=80",
            "kicker": "CORPORATE SERVICES",
            "heading": "Housing solutions for expat and corporate clients",
            "intro": "From single executive lets to full portfolio management for mining, energy and government clients.",
        },
        "services": [
            {"title": "Expat relocation", "body": "Housing search, lease negotiation, orientation tours, and settlement support.", "icon": "Plane"},
            {"title": "Corporate leases", "body": "Bulk residential and commercial leasing with consolidated invoicing.", "icon": "Building2"},
            {"title": "Portfolio management", "body": "Multi-property management, KPI reporting, and quarterly reviews.", "icon": "BarChart3"},
            {"title": "Serviced housing", "body": "Fully furnished, all-inclusive executive residences.", "icon": "Home"},
        ],
    },
    "contact": {
        "hero": {
            "kicker": "CONTACT",
            "heading": "Get in touch",
            "intro": "Reach us during business hours (Mon–Fri, 8am–5pm PGT), or leave a message and we'll respond within one business day.",
        },
        "business_hours": "Mon–Fri, 8am–5pm PGT",
        "map_query": "",
    },
    "legal_privacy": {
        "title": "Privacy Policy",
        "body": "Triumph Real Estate Limited (TREL) values your privacy. This policy explains what information we collect, how we use it, and the choices you have.\n\nWe only collect personal data that you provide to us via our forms (name, email, phone, message, property preferences). We use it to respond to your enquiries, match you with properties, and improve our service.\n\nWe do not sell your data. Your data may be shared with our internal staff and third-party service providers strictly for the purposes above. You can request deletion of your data at any time by emailing sales101.trel@gmail.com.",
    },
    "legal_terms": {
        "title": "Terms of Service",
        "body": "By using the TREL website (\"the Site\"), you agree to these terms.\n\nProperty listings and information on the Site are provided in good faith. While we verify every listing, TREL makes no warranty of accuracy or availability. All prices are indicative and subject to change.\n\nSubmitting a form on the Site does not create a contract of sale or lease. Any transaction must be formalised in a separate written agreement.\n\nAll content on the Site is © Triumph Real Estate Limited and may not be reproduced without permission.",
    },
}


# Migration: overwrite legacy placeholder branding (PNG Realty) with TREL defaults; preserves user edits.
LEGACY_AGENCY_NAMES = {"PNG Realty"}

SAMPLE_REQUIREMENTS = [
    {"customer_name":"Family of 5","intent":"buy","property_type":"house","min_price":600000,"max_price":900000,"min_bedrooms":3,"locations":["Port Moresby"],"notes":"Prefers Gordons or Waigani, secure compound"},
    {"customer_name":"Mining Corporate","intent":"rent","property_type":"apartment","min_price":5000,"max_price":8000,"min_bedrooms":2,"locations":["Port Moresby"],"notes":"Executive housing for FIFO staff","is_corporate":True},
]

async def _seed_users():
    admin_pwd = os.environ.get("ADMIN_PASSWORD", "Admin@123")
    for u in DEMO_USERS:
        exists = await db.users.find_one({"email": u["email"]})
        pwd = admin_pwd if u["role"] == "system_admin" else "Password@123"
        if not exists:
            await db.users.insert_one({"id": new_id(), "email": u["email"], "name": u["name"],
                "role": u["role"], "phone": None, "password_hash": hash_password(pwd), "created_at": now_iso()})
        elif not verify_password(pwd, exists.get("password_hash","")):
            await db.users.update_one({"email": u["email"]}, {"$set": {"password_hash": hash_password(pwd)}})

async def _seed_properties():
    if await db.properties.count_documents({}) == 0:
        for p in DEMO_PROPERTIES:
            await db.properties.insert_one(Property(**p).model_dump())

async def _seed_content():
    for k, v in DEFAULT_CONTENT.items():
        await db.content.update_one({"key": k}, {"$setOnInsert": {"key": k, "value": v}}, upsert=True)
    # Migrate legacy placeholder branding (PNG Realty) → TREL, preserving custom edits
    site = await db.content.find_one({"key": "site"}, {"_id": 0})
    current_name = (site or {}).get("value", {}).get("agency_name", "")
    # Overwrite when: missing agency_name (test corruption), or matches legacy names, or contains "PNG Realty"
    needs_full_reset = (not current_name) or (current_name in LEGACY_AGENCY_NAMES) or ("PNG Realty" in current_name)
    if site and needs_full_reset:
        await db.content.update_one({"key": "site"}, {"$set": {"value": DEFAULT_CONTENT["site"]}})
    else:
        current_logo = (site or {}).get("value", {}).get("logo_url", "")
        if "TREL%20Letter%20Head" in current_logo or "TREL Letter Head" in current_logo:
            await db.content.update_one({"key": "site"}, {"$set": {"value.logo_url": DEFAULT_CONTENT["site"]["logo_url"]}})
        # Add favicon_url / og_image_url / og_description if missing (backfill for older records)
        cur_val = (site or {}).get("value", {}) if site else {}
        backfill = {}
        for k in ("favicon_url", "og_image_url", "og_description"):
            if not cur_val.get(k):
                backfill[f"value.{k}"] = DEFAULT_CONTENT["site"][k]
        if backfill:
            await db.content.update_one({"key": "site"}, {"$set": backfill})
    about = await db.content.find_one({"key": "about"}, {"_id": 0})
    if about and about.get("value", {}).get("heading", "").endswith("PNG Realty"):
        await db.content.update_one({"key": "about"}, {"$set": {"value": DEFAULT_CONTENT["about"]}})
    why = await db.content.find_one({"key": "why"}, {"_id": 0})
    if why and why.get("value", {}).get("heading") == "Why choose us":
        await db.content.update_one({"key": "why"}, {"$set": {"value": DEFAULT_CONTENT["why"]}})

async def _seed_requirements():
    if await db.requirements.count_documents({}) == 0:
        for s in SAMPLE_REQUIREMENTS:
            await db.requirements.insert_one(Requirement(**s).model_dump())

async def _seed_page_content():
    """Seed default per-page content — never overwrites existing edits."""
    for page, defaults in DEFAULT_PAGE_CONTENT.items():
        await db.page_content.update_one(
            {"page": page},
            {"$setOnInsert": {"page": page, "sections": defaults,
                              "updated_at": now_iso(), "updated_by": None}},
            upsert=True,
        )

def _write_test_credentials():
    admin_pwd = os.environ.get("ADMIN_PASSWORD", "Admin@123")
    admin_email = os.environ.get('ADMIN_EMAIL','admin@trel.com.pg')
    try:
        creds_dir = Path("/app/memory")
        creds_dir.mkdir(parents=True, exist_ok=True)
        (creds_dir / "test_credentials.md").write_text(f"""# Triumph Real Estate Limited (TREL) — Test Credentials

## Admin
- Email: `{admin_email}`
- Password: `{admin_pwd}`
- Role: system_admin

## Staff (all password: `Password@123`)
- director@trel.com.pg  (managing_director)
- sales@trel.com.pg     (sales_agent)
- leasing@trel.com.pg   (leasing_agent)
- marketing@trel.com.pg (marketing_officer)

## Auth Endpoints
- POST /api/auth/login  {{ email, password }} -> returns token
- POST /api/auth/logout
- GET  /api/auth/me     (Authorization: Bearer <token>)
""")
    except Exception as e:
        logger.warning(f"Could not write test credentials: {e}")

@app.on_event("startup")
async def on_startup():
    await db.users.create_index("email", unique=True)
    await db.page_content.create_index("page", unique=True)
    _init_storage()
    await _migrate_legacy_user_emails()
    await _seed_users()
    await _seed_properties()
    await _seed_content()
    await _seed_page_content()
    await _seed_requirements()
    _write_test_credentials()
    logger.info("Startup seeding complete")

app.include_router(api)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=False,
    allow_methods=["*"], allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown(): client.close()
