"""All Pydantic domain models — single-file for simplicity."""
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from core.db import new_id, now_iso


# ---- Auth / Users ----
class LoginIn(BaseModel):
    email: EmailStr
    password: str
    turnstile_token: Optional[str] = None


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: str
    phone: Optional[str] = None
    account_category: Literal["STAFF"] = "STAFF"
    status: Literal["PENDING", "ACTIVE", "SUSPENDED", "REJECTED"] = "ACTIVE"
    advertiser_relationship_type: Optional[Literal["OWNER", "JOINT_OWNER", "AUTHORISED_AGENT", "AUTHORISED_REPRESENTATIVE"]] = None


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    phone: Optional[str] = None
    account_category: Optional[Literal["STAFF", "PROPERTY_ADVERTISER", "REFERRAL_PARTNER"]] = None
    status: Optional[Literal["PENDING", "ACTIVE", "SUSPENDED", "REJECTED"]] = None
    advertiser_relationship_type: Optional[Literal["OWNER", "JOINT_OWNER", "AUTHORISED_AGENT", "AUTHORISED_REPRESENTATIVE"]] = None


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
class PropertyDocumentRef(BaseModel):
    document_type: Literal[
        "AUTHORITY_LETTER", "TITLE_DOCUMENT", "OWNER_ID", "LEASE_DOCUMENT", "OTHER"
    ]
    url: str
    name: Optional[str] = None
    status: Literal["UPLOADED", "PENDING_REVIEW", "VERIFIED", "REJECTED"] = "UPLOADED"


class Property(BaseModel):
    id: str = Field(default_factory=new_id)
    title: str
    listing_type: Literal["sale", "rent"]
    property_type: str
    price: float
    currency: Literal["PGK"] = "PGK"
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
    features: List[str] = Field(default_factory=list)
    images: List[str] = Field(default_factory=list)
    status: Literal["draft", "active", "under_offer", "sold", "leased", "withdrawn"] = "draft"
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
    tenure_type: Optional[Literal["STATE_LEASE", "FREEHOLD", "CUSTOMARY", "OTHER"]] = None
    title_reference: Optional[str] = None
    property_type_id: Optional[str] = None
    province_id: Optional[str] = None
    city_id: Optional[str] = None
    suburb_id: Optional[str] = None
    district_id: Optional[str] = None
    local_area_id: Optional[str] = None
    street_id: Optional[str] = None
    owner_name: Optional[str] = None
    owner_email: Optional[str] = None
    owner_phone: Optional[str] = None
    owner_relationship: Literal["OWNER", "JOINT_OWNER", "AUTHORISED_AGENT", "AUTHORISED_REPRESENTATIVE"] = "OWNER"
    authority_status: Literal["PENDING", "VERIFIED", "REJECTED", "EXPIRED"] = "PENDING"
    documents: List[PropertyDocumentRef] = Field(default_factory=list)
    duplicate_override: bool = False
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)

    @field_validator("tenure_type", mode="before")
    @classmethod
    def _empty_tenure_to_none(cls, value):
        if value == "":
            return None
        return value


class PropertyCreate(BaseModel):
    title: str
    listing_type: str
    property_type: str
    price: float
    currency: Literal["PGK"] = "PGK"
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
    features: List[str] = Field(default_factory=list)
    images: List[str] = Field(default_factory=list)
    status: Literal["draft", "active", "under_offer", "sold", "leased", "withdrawn"] = "draft"
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
    tenure_type: Optional[Literal["STATE_LEASE", "FREEHOLD", "CUSTOMARY", "OTHER"]] = None
    title_reference: Optional[str] = None
    property_type_id: Optional[str] = None
    province_id: Optional[str] = None
    city_id: Optional[str] = None
    suburb_id: Optional[str] = None
    district_id: Optional[str] = None
    local_area_id: Optional[str] = None
    street_id: Optional[str] = None
    owner_name: Optional[str] = None
    owner_email: Optional[str] = None
    owner_phone: Optional[str] = None
    owner_relationship: Literal["OWNER", "JOINT_OWNER", "AUTHORISED_AGENT", "AUTHORISED_REPRESENTATIVE"] = "OWNER"
    authority_status: Literal["PENDING", "VERIFIED", "REJECTED", "EXPIRED"] = "PENDING"
    documents: List[PropertyDocumentRef] = Field(default_factory=list)
    duplicate_override: bool = False

    @field_validator("tenure_type", mode="before")
    @classmethod
    def _empty_tenure_to_none(cls, value):
        if value == "":
            return None
        return value


class PropertyReferralCreate(BaseModel):
    property_id: Optional[str] = None
    owner_name: str
    owner_phone: Optional[str] = None
    owner_email: Optional[EmailStr] = None
    source_relationship: Literal["OWNER", "JOINT_OWNER"]
    direct_from_owner: Literal[True]
    notes: Optional[str] = ""


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
    mine: Optional[bool] = None
    limit: int = 60


# ---- Property Data Aggregation ----
class MarketSourceCreate(BaseModel):
    name: str
    domain: str
    base_url: Optional[str] = None
    active: bool = True
    is_trel_owned: bool = False
    collector_key: Optional[str] = None
    listing_pages: List[Dict[str, Any]] = Field(default_factory=list)
    parser_config: Dict[str, Any] = Field(default_factory=dict)


class MarketObservationCreate(BaseModel):
    source_site_id: str
    source_listing_id: str
    source_url: str
    observed_at: Optional[str] = None
    current_status: Literal[
        "ACTIVE", "NOT_SEEN", "REMOVED", "RELISTED", "SOLD_CONFIRMED",
        "RENTED_CONFIRMED", "WITHDRAWN_CONFIRMED", "UNKNOWN",
    ] = "ACTIVE"
    transaction_type: Literal["SALE", "RENT"]
    property_type_id: Optional[str] = None
    property_type_name: Optional[str] = None
    province_id: Optional[str] = None
    province_name: Optional[str] = None
    district_id: Optional[str] = None
    district_name: Optional[str] = None
    city_id: Optional[str] = None
    city_name: Optional[str] = None
    suburb_id: Optional[str] = None
    suburb_name: Optional[str] = None
    local_area_id: Optional[str] = None
    local_area_name: Optional[str] = None
    street_name: Optional[str] = None
    location_name: Optional[str] = None
    lot: Optional[str] = None
    section: Optional[str] = None
    portion: Optional[str] = None
    owner_name: Optional[str] = None
    bedrooms: Optional[int] = Field(default=None, ge=0)
    bathrooms: Optional[int] = Field(default=None, ge=0)
    land_area_sqm: Optional[float] = Field(default=None, gt=0)
    building_area_sqm: Optional[float] = Field(default=None, gt=0)
    price_amount: Optional[float] = Field(default=None, gt=0)
    currency: Literal["PGK"] = "PGK"
    price_type: Literal[
        "FIXED", "NEGOTIABLE", "FROM", "RANGE", "POA", "TENDER",
        "EOI", "AUCTION", "UNKNOWN",
    ] = "FIXED"
    rental_period: Optional[Literal["DAY", "WEEK", "FORTNIGHT", "MONTH", "YEAR"]] = None
    trel_property_id: Optional[str] = None
    raw_payload: Dict[str, Any] = Field(default_factory=dict)


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
    property_id: Optional[str] = None
    property_type: str
    listing_type: str
    price: float
    province: Optional[str] = None
    city: Optional[str] = None
    suburb: Optional[str] = None
    local_area: Optional[str] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    parking: Optional[int] = None
    land_area_sqm: Optional[float] = None
    building_area_sqm: Optional[float] = None
    property_condition: Optional[str] = None
    tenure_type: Optional[str] = None
    street_name: Optional[str] = None
    nearby_landmark: Optional[str] = None


class NearbyAmenitiesIn(BaseModel):
    suburb: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    property_type: Optional[str] = None
