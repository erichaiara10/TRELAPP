"""CSV import/export for Properties and Customers.

- Import is APPEND-ONLY: rows with an existing `id` are skipped (never overwritten).
- All strict validation from routes/properties.py + routes/customers.py is reused
  so CSV imports behave identically to interactive UI create calls.
- Import Guide (`GET /admin/{entity}/csv/schema`) is the single source of truth
  for the "Import Guide" table on the admin pages.
"""
import csv
import io
import json
from typing import Any, Callable

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from core.db import db, new_id, now_iso
from core.security import get_current_user
from models import Customer, CustomerCreate, Property, PropertyCreate
from routes.customers import _validate_customer
from routes.properties import enforce_scheme

router = APIRouter()


# ---- Schema definitions (single source of truth for header, guide, export) ----
PROPERTY_SCHEMA = [
    ("id",                  "auto",        "Leave blank for new rows. Auto-generated UUID."),
    ("title",               "mandatory",   "Public-facing property name (max 120 chars)."),
    ("listing_type",        "mandatory",   "Exactly 'sale' or 'rent'."),
    ("property_type",       "mandatory",   "Must match an existing property_types.name (e.g. House, Apartment, Large Land – Portion / Customary)."),
    ("price",               "mandatory",   "PGK amount, integer or decimal, MUST be > 0."),
    ("currency",            "optional",    "Defaults to PGK."),
    ("bedrooms",            "optional",    "Integer count."),
    ("bathrooms",           "optional",    "Integer count."),
    ("parking",             "optional",    "Integer count of parking bays."),
    ("area_sqm",            "optional",    "Building/lot area in square metres."),
    ("province",            "mandatory",   "e.g. National Capital District."),
    ("location",            "mandatory",   "City — e.g. Port Moresby, Lae, Madang."),
    ("suburb",              "mandatory",   "Neighbourhood — e.g. Waigani, Gordons."),
    ("address",             "optional",    "Human-readable street address."),
    ("allotment_number",    "conditional", "REQUIRED if the property_type's legal_scheme is 'lot_section_street'."),
    ("section_number",      "conditional", "REQUIRED if the property_type's legal_scheme is 'lot_section_street'."),
    ("street_name",         "conditional", "REQUIRED if the property_type's legal_scheme is 'lot_section_street'."),
    ("full_portion_number", "conditional", "REQUIRED if the property_type's legal_scheme is 'portion'."),
    ("total_area_ha",       "conditional", "REQUIRED for sale listings. Decimal hectares (up to 4dp)."),
    ("nearby_landmark",     "optional",    "e.g. next to Vision City."),
    ("map_coords",          "optional",    "Latitude,Longitude — e.g. -9.4438,147.1803."),
    ("description",         "optional",    "Free text (multi-line — wrap in quotes if it contains commas)."),
    ("features",            "optional",    "Semicolon-separated list, e.g. Pool;Fenced;Solar."),
    ("images",              "optional",    "Semicolon-separated URLs."),
    ("status",              "optional",    "Defaults to 'active'. One of: draft, active, under_offer, sold, leased, withdrawn."),
    ("featured",            "optional",    "true or false. Defaults to false."),
    ("verified",            "optional",    "true or false. Defaults to false."),
    ("owner_customer_id",   "optional",    "UUID of an existing customer."),
    ("assigned_agent_id",   "optional",    "UUID of an existing user."),
    ("created_at",          "auto",        "ISO 8601 timestamp — auto-generated if blank."),
]

CUSTOMER_SCHEMA = [
    ("id",                 "auto",       "Leave blank for new rows. Auto-generated UUID."),
    ("name",               "mandatory",  "Full name of the customer or company contact."),
    ("email",              "mandatory",  "Valid email address."),
    ("phone",              "mandatory",  "PNG phone format — 8 digits (mobile) or with area code."),
    ("customer_type",      "mandatory",  "One of: buyer, seller, tenant, landlord, corporate."),
    ("company",            "optional",   "Company name for corporate clients."),
    ("notes",              "optional",   "Free-text notes visible to staff only."),
    ("source",             "optional",   "Defaults to 'import'. e.g. sell_form, wanted_form, manual, import."),
    ("assigned_agent_id",  "optional",   "UUID of an existing user."),
    ("created_at",         "auto",       "ISO 8601 timestamp — auto-generated if blank."),
]

_SCHEMAS = {"properties": PROPERTY_SCHEMA, "customers": CUSTOMER_SCHEMA}


def _headers(entity: str) -> list[str]:
    return [f for f, _, _ in _SCHEMAS[entity]]


def _required_headers(entity: str) -> list[str]:
    """Headers the CSV MUST include (mandatory + conditional). Auto/optional may be omitted."""
    return [f for f, kind, _ in _SCHEMAS[entity] if kind in ("mandatory", "conditional")]


# ---- Row parsers (CSV string → dict) ----
LIST_SEP = ";"


def _to_bool(v: Any) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "y")


def _to_number(v: Any, cast: Callable, default=0):
    if v is None or str(v).strip() == "":
        return default
    try:
        return cast(str(v).strip())
    except (ValueError, TypeError):
        raise ValueError(f"expected a number, got '{v}'")


def _to_list(v: Any) -> list[str]:
    if v is None or str(v).strip() == "":
        return []
    return [p.strip() for p in str(v).split(LIST_SEP) if p.strip()]


def _row_to_property(row: dict) -> dict:
    """Convert one CSV row to a property payload ready for enforce_scheme + insert."""
    out: dict[str, Any] = {}
    for k in ("id", "title", "listing_type", "property_type", "currency",
              "province", "location", "suburb", "address",
              "allotment_number", "section_number", "street_name",
              "full_portion_number", "nearby_landmark", "map_coords",
              "description", "status", "owner_customer_id", "assigned_agent_id",
              "created_at"):
        v = row.get(k)
        out[k] = str(v).strip() if v is not None and str(v).strip() != "" else None
    out["price"] = _to_number(row.get("price"), float, default=0.0)
    out["bedrooms"] = int(_to_number(row.get("bedrooms"), float, default=0))
    out["bathrooms"] = int(_to_number(row.get("bathrooms"), float, default=0))
    out["parking"] = int(_to_number(row.get("parking"), float, default=0))
    out["area_sqm"] = _to_number(row.get("area_sqm"), float, default=0.0) or None
    out["total_area_ha"] = _to_number(row.get("total_area_ha"), float, default=0.0) or None
    out["featured"] = _to_bool(row.get("featured"))
    out["verified"] = _to_bool(row.get("verified"))
    out["features"] = _to_list(row.get("features"))
    out["images"] = _to_list(row.get("images"))
    if not out["currency"]:
        out["currency"] = "PGK"
    if not out["status"]:
        out["status"] = "active"
    return out


def _row_to_customer(row: dict) -> dict:
    out = {}
    for k in ("id", "name", "email", "phone", "customer_type", "company",
              "notes", "source", "assigned_agent_id", "created_at"):
        v = row.get(k)
        out[k] = str(v).strip() if v is not None and str(v).strip() != "" else None
    if not out["customer_type"]:
        out["customer_type"] = "buyer"
    if not out["source"]:
        out["source"] = "import"
    if not out["notes"]:
        out["notes"] = ""
    return out


# ---- Row serialisers (Mongo doc → CSV cell) ----
def _fmt_cell(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, list):
        return LIST_SEP.join(str(x) for x in v)
    if isinstance(v, dict):
        return json.dumps(v, separators=(",", ":"), ensure_ascii=False)
    return str(v)


# ---- Import Guide + Template endpoints ----
@router.get("/admin/{entity}/csv/schema")
async def get_csv_schema(entity: str, user: dict = Depends(get_current_user)):
    if entity not in _SCHEMAS:
        raise HTTPException(404, "Unknown entity")
    return {
        "entity": entity,
        "list_separator": LIST_SEP,
        "fields": [{"name": n, "type": t, "explanation": e}
                   for n, t, e in _SCHEMAS[entity]],
        "required_headers": _required_headers(entity),
    }


@router.get("/admin/{entity}/csv/template")
async def get_csv_template(entity: str, user: dict = Depends(get_current_user)):
    if entity not in _SCHEMAS:
        raise HTTPException(404, "Unknown entity")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(_headers(entity))  # just the header row — empty template
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{entity}_template.csv"'},
    )


# ---- Export endpoints ----
@router.get("/admin/{entity}/csv")
async def export_csv(entity: str, user: dict = Depends(get_current_user)):
    if entity not in _SCHEMAS:
        raise HTTPException(404, "Unknown entity")
    coll = getattr(db, entity)
    docs = await coll.find({}, {"_id": 0}).sort("created_at", -1).to_list(50000)
    fields = _headers(entity)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(fields)
    for d in docs:
        w.writerow([_fmt_cell(d.get(f)) for f in fields])
    buf.seek(0)
    date_stamp = now_iso().split("T")[0]
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition":
                 f'attachment; filename="{entity}_{date_stamp}.csv"'},
    )


# ---- Import endpoint ----
def _read_csv(file_bytes: bytes) -> tuple[list[str], list[dict]]:
    text = file_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    headers = list(reader.fieldnames or [])
    rows = list(reader)
    return headers, rows


def _validate_headers(entity: str, headers: list[str]) -> list[str]:
    required = _required_headers(entity)
    missing = [h for h in required if h not in headers]
    return missing


async def _import_properties(rows: list[dict]) -> dict:
    inserted, skipped, errors = 0, [], []
    for i, raw in enumerate(rows, start=2):  # start=2 → line 1 is the header
        try:
            row = _row_to_property(raw)
            existing_id = row.get("id")
            if existing_id and await db.properties.find_one({"id": existing_id}, {"_id": 0, "id": 1}):
                skipped.append({"row": i, "reason": f"id '{existing_id}' already exists"})
                continue
            # Reuse the same strict validation as the interactive UI
            data = await enforce_scheme(row)
            if not existing_id:
                data.pop("id", None)
            if not data.get("created_at"):
                data.pop("created_at", None)
            p = Property(**{k: v for k, v in data.items() if v is not None or k in
                            ("images", "features")}).model_dump()
            if existing_id:
                p["id"] = existing_id
            await db.properties.insert_one(p)
            inserted += 1
        except HTTPException as he:
            errors.append({"row": i, "reason": he.detail})
        except Exception as e:
            errors.append({"row": i, "reason": str(e)[:200]})
    return {"inserted": inserted, "skipped": skipped, "errors": errors}


async def _import_customers(rows: list[dict]) -> dict:
    inserted, skipped, errors = 0, [], []
    for i, raw in enumerate(rows, start=2):
        try:
            row = _row_to_customer(raw)
            existing_id = row.get("id")
            if existing_id and await db.customers.find_one({"id": existing_id}, {"_id": 0, "id": 1}):
                skipped.append({"row": i, "reason": f"id '{existing_id}' already exists"})
                continue
            payload = CustomerCreate(**{k: row.get(k) for k in
                ("name", "email", "phone", "customer_type", "company",
                 "notes", "source", "assigned_agent_id")})
            _validate_customer(payload)
            c = Customer(**payload.model_dump()).model_dump()
            if existing_id:
                c["id"] = existing_id
            if row.get("created_at"):
                c["created_at"] = row["created_at"]
            await db.customers.insert_one(c)
            inserted += 1
        except HTTPException as he:
            errors.append({"row": i, "reason": he.detail})
        except Exception as e:
            errors.append({"row": i, "reason": str(e)[:200]})
    return {"inserted": inserted, "skipped": skipped, "errors": errors}


_IMPORTERS = {"properties": _import_properties, "customers": _import_customers}


@router.post("/admin/{entity}/csv")
async def import_csv(entity: str, file: UploadFile = File(...),
                     user: dict = Depends(get_current_user)):
    if entity not in _IMPORTERS:
        raise HTTPException(404, "Unknown entity")
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "File must be a .csv")
    raw = await file.read()
    if len(raw) > 20 * 1024 * 1024:  # 20 MB
        raise HTTPException(400, "File too large (max 20 MB)")
    try:
        headers, rows = _read_csv(raw)
    except UnicodeDecodeError:
        raise HTTPException(400, "CSV must be UTF-8 encoded")
    if not headers:
        raise HTTPException(400, "CSV is empty or missing a header row")
    missing = _validate_headers(entity, headers)
    if missing:
        raise HTTPException(400, f"CSV is missing required headers: {', '.join(missing)}")
    if not rows:
        return {"inserted": 0, "skipped": [], "errors": [],
                "message": "No data rows found — nothing imported."}
    result = await _IMPORTERS[entity](rows)
    result["received"] = len(rows)
    return result
