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

from fastapi import FastAPI, APIRouter, Request, Response, HTTPException, Depends
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALG = os.environ.get("JWT_ALGORITHM", "HS256")

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

app = FastAPI(title="PNG Realty API")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pngrealty")

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

@api.get("/properties")
async def list_properties(
    listing_type: Optional[str] = None, property_type: Optional[str] = None,
    location: Optional[str] = None, min_price: Optional[float] = None,
    max_price: Optional[float] = None, bedrooms: Optional[int] = None,
    featured: Optional[bool] = None, status: Optional[str] = "active",
    q: Optional[str] = None, limit: int = 60,
):
    query = _build_property_query({
        "listing_type": listing_type, "property_type": property_type, "location": location,
        "min_price": min_price, "max_price": max_price, "bedrooms": bedrooms,
        "featured": featured, "status": status, "q": q,
    })
    return await db.properties.find(query, {"_id":0}).sort("created_at",-1).to_list(limit)

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
async def root(): return {"ok": True, "service": "PNG Realty API"}

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
    {"email": os.environ.get("ADMIN_EMAIL","admin@pngrealty.pg"), "name":"System Admin","role":"system_admin"},
    {"email":"director@pngrealty.pg","name":"Naomi Kila","role":"managing_director"},
    {"email":"sales@pngrealty.pg","name":"John Namaliu","role":"sales_agent"},
    {"email":"leasing@pngrealty.pg","name":"Grace Toua","role":"leasing_agent"},
    {"email":"marketing@pngrealty.pg","name":"Peter Amet","role":"marketing_officer"},
]

DEFAULT_CONTENT = {
    "site": {"agency_name":"PNG Realty","tagline":"Homes rooted in the heart of Papua New Guinea",
             "phone":"+675 7100 0000","whatsapp":"6757100000","email":"hello@pngrealty.pg",
             "address":"Level 4, Deloitte Tower, Port Moresby, NCD"},
    "about": {"heading":"About PNG Realty","body":"We are a locally-owned Papua New Guinea real estate agency helping families, investors and corporates find the right home, tenant or asset. Our team combines deep local knowledge with modern, transparent processes."},
    "why": {"heading":"Why choose us","items":[
        {"title":"Local expertise","body":"Born and raised in PNG — we know every suburb, security landscape, and school catchment."},
        {"title":"Verified listings","body":"Every property is checked by our team before it goes live."},
        {"title":"Corporate ready","body":"We handle expat relocations, corporate leases and portfolio management end-to-end."},
    ]},
}

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

async def _seed_requirements():
    if await db.requirements.count_documents({}) == 0:
        for s in SAMPLE_REQUIREMENTS:
            await db.requirements.insert_one(Requirement(**s).model_dump())

def _write_test_credentials():
    admin_pwd = os.environ.get("ADMIN_PASSWORD", "Admin@123")
    try:
        creds_dir = Path("/app/memory")
        creds_dir.mkdir(parents=True, exist_ok=True)
        (creds_dir / "test_credentials.md").write_text(f"""# PNG Realty Test Credentials

## Admin
- Email: `{os.environ.get('ADMIN_EMAIL','admin@pngrealty.pg')}`
- Password: `{admin_pwd}`
- Role: system_admin

## Staff (all password: `Password@123`)
- director@pngrealty.pg  (managing_director)
- sales@pngrealty.pg     (sales_agent)
- leasing@pngrealty.pg   (leasing_agent)
- marketing@pngrealty.pg (marketing_officer)

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
    await _seed_users()
    await _seed_properties()
    await _seed_content()
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
