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
    # Market-intelligence identity graph (Phase 1 — Data Aggregation)
    master_property_id: Optional[str] = None
    property_unit_id: Optional[str] = None
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


# =====================================================================
# Market Intelligence / Data Aggregation (Phase 1)
# Implements TRELPNG algorithm specs:
#   * MATCH-1.0  — Duplicate Matching & Property Identity
#   * GUIDE-1.0  — Comparable Property Selection & Market Price Guidance
# =====================================================================


# ---- Market Sources (configured scrapers / data feeds) ----
class MarketSource(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str
    base_url: Optional[str] = None
    description: Optional[str] = ""
    # Per-source safety switch — see algo doc §28
    allow_source_auto_match: bool = True
    active: bool = True
    # Which collector implementation drives this source (see core/collectors)
    collector: str = "seed"
    # ERD fields for scheduling + health metrics
    collection_frequency: Literal["manual", "hourly", "daily", "weekly"] = "manual"
    parser_version: Optional[str] = "1.0"
    last_run_at: Optional[str] = None
    last_successful_run_at: Optional[str] = None
    consecutive_failures: int = 0
    # Free-form scraper knobs — CSS selectors, custom pagination templates,
    # user-agent overrides. Every HttpListingCollector reads from here so
    # operators can tune extraction via the admin UI without touching code.
    # NOTE: `search_paths` are NO LONGER stored here — see `listing_pages`
    # below. Discovery is now mandatory for HTTP scrapers.
    parser_config: dict = {}
    # Confirmed listing category URLs — populated by the "Discover Pages"
    # workflow. Each entry is:
    #   {category, category_label, listing_url, purpose?, cards_found?}
    # `listing_url` is stored as the EXACT literal URL returned by discovery
    # (post-redirect) and used verbatim by the scraper — no reconstruction.
    listing_pages: List[dict] = []
    # Seed-generator-only: how many synthetic listings to emit per run.
    seed_count: Optional[int] = None
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class MarketSourceCreate(BaseModel):
    name: str
    base_url: Optional[str] = None
    description: Optional[str] = ""
    allow_source_auto_match: bool = True
    active: bool = True
    collector: str = "seed"
    collection_frequency: Literal["manual", "hourly", "daily", "weekly"] = "manual"
    parser_version: Optional[str] = "1.0"
    parser_config: dict = {}
    listing_pages: List[dict] = []
    seed_count: Optional[int] = None


# ---- Collection runs (scrape audit) ----
class CollectionRun(BaseModel):
    id: str = Field(default_factory=new_id)
    source_id: str
    run_type: Literal["scheduled", "manual", "backfill"] = "manual"
    triggered_by: Optional[str] = None       # user_id or scheduler tag
    started_at: str = Field(default_factory=now_iso)
    finished_at: Optional[str] = None
    duration_ms: Optional[int] = None
    status: Literal["running", "success", "failed", "partial"] = "running"
    listings_seen: int = 0
    listings_new: int = 0
    listings_updated: int = 0
    matches_created: int = 0
    review_cases_created: int = 0
    errors: List[str] = []
    parser_version: Optional[str] = None
    algorithm_version: str = "MATCH-1.0"


# ---- Market Listings (raw source ads) ----
class MarketListing(BaseModel):
    id: str = Field(default_factory=new_id)
    source_id: str
    source_listing_id: str
    source_url: Optional[str] = None
    purpose: Optional[Literal["sale", "rent"]] = None
    raw_fields: dict = {}
    normalized_fields: dict = {}
    price: Optional[float] = None
    currency: str = "PGK"
    rent_period: Optional[Literal["monthly", "weekly", "fortnightly", "daily", "annual"]] = None
    property_class: Optional[str] = None       # residential / commercial_industrial / vacant_land / etc
    property_subtype: Optional[str] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    land_area_m2: Optional[float] = None
    building_area_m2: Optional[float] = None
    allotment_number: Optional[str] = None
    section_number: Optional[str] = None
    portion_number: Optional[str] = None
    street: Optional[str] = None
    suburb: Optional[str] = None
    local_area: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    gps_accuracy: Optional[str] = None
    first_seen: str = Field(default_factory=now_iso)
    last_seen: str = Field(default_factory=now_iso)
    status: Literal["active", "inactive", "excluded", "unresolved"] = "active"
    exclusion_reason: Optional[str] = None
    alias_map_version: Optional[str] = None
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


# ---- Listing snapshots (price/status history) ----
class MarketListingSnapshot(BaseModel):
    id: str = Field(default_factory=new_id)
    market_listing_id: str
    observed_at: str = Field(default_factory=now_iso)
    price: Optional[float] = None
    rent_period: Optional[str] = None
    status: Optional[str] = None
    raw_snapshot: dict = {}


# ---- Master Property (persistent parcel/site/building identity) ----
class MasterProperty(BaseModel):
    id: str = Field(default_factory=new_id)
    property_class: Optional[str] = None
    property_subtype: Optional[str] = None
    allotment_number: Optional[str] = None
    section_number: Optional[str] = None
    portion_number: Optional[str] = None
    street: Optional[str] = None
    suburb: Optional[str] = None
    local_area: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    building_name: Optional[str] = None
    land_area_m2: Optional[float] = None
    building_area_m2: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    canonical_fields: dict = {}               # winning values + provenance
    trel_property_id: Optional[str] = None    # link back to /properties record
    is_vacant: Optional[bool] = None
    algorithm_version: str = "MATCH-1.0"
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class MasterPropertyCreate(BaseModel):
    property_class: Optional[str] = None
    property_subtype: Optional[str] = None
    allotment_number: Optional[str] = None
    section_number: Optional[str] = None
    portion_number: Optional[str] = None
    street: Optional[str] = None
    suburb: Optional[str] = None
    local_area: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    building_name: Optional[str] = None
    land_area_m2: Optional[float] = None
    building_area_m2: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    trel_property_id: Optional[str] = None
    is_vacant: Optional[bool] = None


# ---- Property Unit (child of Master Property) ----
class PropertyUnit(BaseModel):
    id: str = Field(default_factory=new_id)
    master_property_id: str
    unit_number: Optional[str] = None
    floor: Optional[str] = None
    building_name: Optional[str] = None
    subtype: Optional[str] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    building_area_m2: Optional[float] = None
    trel_property_id: Optional[str] = None
    canonical_fields: dict = {}
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class PropertyUnitCreate(BaseModel):
    master_property_id: str
    unit_number: Optional[str] = None
    floor: Optional[str] = None
    building_name: Optional[str] = None
    subtype: Optional[str] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    building_area_m2: Optional[float] = None
    trel_property_id: Optional[str] = None


# ---- Property Match (market_listing -> master/unit, reversible) ----
class PropertyMatch(BaseModel):
    id: str = Field(default_factory=new_id)
    market_listing_id: str
    master_property_id: Optional[str] = None
    property_unit_id: Optional[str] = None
    method: Literal["exact_source", "D1", "D2", "D3", "D4", "D5", "D6", "weighted", "manual"] = "weighted"
    decision_band: Literal[
        "certain", "automatic", "probable", "possible", "no_match", "conflict_review"
    ] = "automatic"
    score: float = 0.0
    signals: dict = {}
    conflicts: List[str] = []
    algorithm_version: str = "MATCH-1.0"
    config_version: Optional[str] = None
    status: Literal["active", "detached", "superseded"] = "active"
    reviewer_id: Optional[str] = None
    reviewer_note: Optional[str] = None
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


# ---- Market Review Cases (manual queue) ----
class MarketReviewCase(BaseModel):
    id: str = Field(default_factory=new_id)
    case_type: Literal[
        "probable", "possible", "conflict", "split_request", "merge_request", "manual"
    ] = "probable"
    market_listing_id: Optional[str] = None
    proposed_master_property_id: Optional[str] = None
    proposed_property_unit_id: Optional[str] = None
    score: Optional[float] = None
    conflicts: List[str] = []
    payload: dict = {}
    status: Literal["open", "in_review", "resolved", "dismissed"] = "open"
    resolution: Optional[str] = None
    reviewer_id: Optional[str] = None
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


# ---- Audit Events (immutable) ----
class MarketAuditEvent(BaseModel):
    id: str = Field(default_factory=new_id)
    event_type: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    payload: dict = {}
    reason: Optional[str] = None
    actor_id: Optional[str] = None
    algorithm_version: Optional[str] = None
    config_version: Optional[str] = None
    created_at: str = Field(default_factory=now_iso)


# ---- Location Reference (canonical hierarchy + aliases) ----
class LocationReference(BaseModel):
    id: str = Field(default_factory=new_id)
    province: Optional[str] = None
    district: Optional[str] = None
    city: Optional[str] = None
    suburb: Optional[str] = None
    local_area: Optional[str] = None
    street: Optional[str] = None
    aliases: List[str] = []
    canonical: bool = True
    created_at: str = Field(default_factory=now_iso)


# ---- Market Configuration (versioned params) ----
class MarketConfiguration(BaseModel):
    id: str = Field(default_factory=new_id)
    version: str
    algorithm: Literal["match", "guidance", "combined"] = "combined"
    active: bool = True
    parameters: dict = {}
    notes: Optional[str] = ""
    created_at: str = Field(default_factory=now_iso)
    created_by: Optional[str] = None


class MarketConfigurationCreate(BaseModel):
    version: str
    algorithm: Literal["match", "guidance", "combined"] = "combined"
    parameters: dict
    notes: Optional[str] = ""
    activate: bool = True


# ---- Guidance Engine (schemas only — populated in Phase C) ----
class ValuationRequest(BaseModel):
    id: str = Field(default_factory=new_id)
    subject_property_id: Optional[str] = None
    subject_master_property_id: Optional[str] = None
    subject_property_unit_id: Optional[str] = None
    subject_snapshot: dict = {}
    purpose: Literal["sale", "rent"] = "sale"
    workflow: Literal["seller", "buyer", "landlord", "renter", "admin"] = "admin"
    requestor_user_id: Optional[str] = None
    algorithm_version: str = "GUIDE-1.0"
    config_version: Optional[str] = None
    created_at: str = Field(default_factory=now_iso)


class GuidanceResult(BaseModel):
    id: str = Field(default_factory=new_id)
    valuation_request_id: str
    comparable_count: int = 0
    observed_range: dict = {}                # {"min": .., "max": ..}
    median: Optional[float] = None
    weighted_median: Optional[float] = None
    trel_indicative_range: dict = {}         # {"p25": .., "p75": ..}
    confidence_score: Optional[float] = None
    confidence_label: Literal["insufficient", "limited", "moderate", "strong"] = "insufficient"
    supporting_evidence_count: int = 0
    outputs: dict = {}
    algorithm_version: str = "GUIDE-1.0"
    config_version: Optional[str] = None
    created_at: str = Field(default_factory=now_iso)


class GuidanceComparable(BaseModel):
    id: str = Field(default_factory=new_id)
    guidance_result_id: str
    master_property_id: Optional[str] = None
    property_unit_id: Optional[str] = None
    market_listing_id: Optional[str] = None
    tier: Literal["same_street", "same_local_area", "same_suburb", "supporting"] = "same_suburb"
    quality_score: float = 0.0
    recency_factor: float = 1.0
    effective_weight: float = 0.0
    value: Optional[float] = None
    inclusion_status: Literal[
        "included", "excluded_outlier", "excluded_quality", "excluded_manual"
    ] = "included"
    exclusion_reason: Optional[str] = None
    cqs_breakdown: dict = {}                # {location, class_subtype, size, features, condition, recency}
    months_since: Optional[float] = None
    snapshot: dict = {}                     # denormalised candidate view: bedrooms, land_area_m2, building_area_m2, suburb, property_subtype
