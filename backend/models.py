"""All Pydantic domain models — single-file for simplicity."""
from typing import List, Literal, Optional

from pydantic import BaseModel, EmailStr, Field

from core.db import new_id, now_iso


# ---- Auth / Users ----
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


# ---- Communications ----
# `parent_type` + `parent_id` let us log against either a lead or a customer.
# `lead_id` retained for backward compatibility with existing docs.
class Communication(BaseModel):
    id: str = Field(default_factory=new_id)
    parent_type: Literal["lead", "customer"] = "lead"
    parent_id: str
    lead_id: Optional[str] = None       # legacy — mirrors parent_id when parent_type='lead'
    customer_id: Optional[str] = None   # convenience — mirrors parent_id when parent_type='customer'
    kind: Literal["call", "email", "whatsapp", "note", "meeting", "sms"] = "note"
    direction: Literal["inbound", "outbound", "internal"] = "outbound"
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


# ---- Property ----
class Property(BaseModel):
    id: str = Field(default_factory=new_id)
    title: str
    listing_type: Literal["sale", "rent"]
    property_type: str
    price: float
    currency: str = "PGK"
    bedrooms: Optional[int] = 0
    bathrooms: Optional[int] = 0
    parking: Optional[int] = 0
    area_sqm: Optional[float] = None
    location: str
    suburb: Optional[str] = None
    province: Optional[str] = None
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
    # Legal & location details
    full_portion_number: Optional[str] = None
    allotment_number: Optional[str] = None
    section_number: Optional[str] = None
    total_area_ha: Optional[float] = None
    street_name: Optional[str] = None
    nearby_landmark: Optional[str] = None
    district: Optional[str] = None
    local_area: Optional[str] = None
    tenure_type: Optional[str] = None
    title_reference: Optional[str] = None
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
    province: Optional[str] = None
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
    full_portion_number: Optional[str] = None
    allotment_number: Optional[str] = None
    section_number: Optional[str] = None
    total_area_ha: Optional[float] = None
    street_name: Optional[str] = None
    nearby_landmark: Optional[str] = None
    district: Optional[str] = None
    local_area: Optional[str] = None
    tenure_type: Optional[str] = None
    title_reference: Optional[str] = None


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


# ---- Customer ----
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


# ---- Property Types (dynamic) ----
class PropertyType(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str
    legal_scheme: Literal["lot_section_street", "portion"] = "lot_section_street"
    order: int = 100
    is_active: bool = True
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class PropertyTypeCreate(BaseModel):
    name: str
    legal_scheme: Literal["lot_section_street", "portion"] = "lot_section_street"
    order: Optional[int] = 100
    is_active: bool = True


# ---- Requirements ----
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


# ---- Leads ----
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
    converted_at: Optional[str] = None
    converted_property_id: Optional[str] = None
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


# ---- Inspections ----
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


# ---- Tasks ----
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


# ---- Locations ----
class ProvinceIn(BaseModel):
    name: str


class CityIn(BaseModel):
    name: str
    province_id: str


class SuburbIn(BaseModel):
    name: str
    city_id: str


class RenameIn(BaseModel):
    name: str


# ---- AI ----
class PriceAnalysisIn(BaseModel):
    property_type: str
    listing_type: str
    price: float
    province: Optional[str] = None
    city: Optional[str] = None
    suburb: Optional[str] = None
    bedrooms: Optional[int] = None
    street_name: Optional[str] = None
    nearby_landmark: Optional[str] = None


class NearbyAmenitiesIn(BaseModel):
    suburb: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    property_type: Optional[str] = None
