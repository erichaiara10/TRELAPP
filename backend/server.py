import asyncio
import contextlib
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

"""TREL API — application entry point.

The heavy lifting lives in `routes/` (endpoints), `core/` (db + auth + notify),
`models.py` (Pydantic schemas), `seed_data.py` (static defaults), and
`seed.py` (startup migrations).
"""
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import logging

from fastapi import APIRouter
from starlette.middleware.cors import CORSMiddleware

from core.db import client, detect_topology, strict_transactions_required
from core.login_guard import ensure_indexes as ensure_login_guard_indexes
from routes import (
    advertiser, ai, auth, content, csv_io, customers, files, inspections, leads, locations,
    market, matching, properties, property_types, public, referrals, reports, requirements, tasks,
    staff_property_advertising,
)
from seed import run_startup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("trel")

app = FastAPI(title="TREL API")
api = APIRouter(prefix="/api")

# Mount every route file's router onto the shared /api prefix
for module in (
    auth, properties, property_types, customers, requirements,
    leads, inspections, tasks, matching, locations,
    ai, content, reports, public, referrals, market, files, csv_io, advertiser,
    staff_property_advertising,
):
    api.include_router(module.router)


@api.get("/")
async def root():
    return {"ok": True, "service": "TREL API"}


_lifecycle_task = None


@app.on_event("startup")
async def on_startup():
    global _lifecycle_task
    files.init_storage()
    await run_startup()
    await ensure_login_guard_indexes()
    await market.ensure_market_indexes()
    await market.resume_pending_collection_runs()
    await staff_property_advertising.ensure_indexes()
    await staff_property_advertising.run_lifecycle_maintenance()
    _lifecycle_task = asyncio.create_task(staff_property_advertising.lifecycle_maintenance_loop())
    topology = await detect_topology()
    strict = strict_transactions_required()
    mode = "TRANSACTIONAL" if topology.get("supports_transactions") else "NON_TRANSACTIONAL_FALLBACK"
    logger.info(
        "MongoDB topology=%s set_name=%s write_mode=%s strict=%s",
        topology.get("kind"), topology.get("set_name"), mode, strict,
    )
    if not topology.get("supports_transactions") and strict:
        raise RuntimeError(
            f"TREL_MONGO_STRICT_TRANSACTIONS is on (or Atlas URI detected) but "
            f"MongoDB topology is {topology.get('kind')}. Refusing to start with "
            f"non-transactional fallback."
        )


@app.on_event("shutdown")
async def shutdown():
    if _lifecycle_task:
        _lifecycle_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _lifecycle_task
    client.close()


app.include_router(api)


def _resolved_origins() -> list[str]:
    raw = os.getenv("TREL_ALLOWED_ORIGINS", "").strip()
    if not raw:
        return ["*"]
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


_origins = _resolved_origins()
_credentialed = _origins != ["*"]
logger.info("CORS origins=%s allow_credentials=%s", _origins, _credentialed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=_credentialed,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- SERVE FRONTEND STATIC FILES (SAFE FALLBACK) ---
frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../frontend"))

if os.path.exists(frontend_path):
    _static_dir = os.path.join(frontend_path, "static")
    if os.path.isdir(_static_dir):
        app.mount("/static", StaticFiles(directory=_static_dir), name="static")

@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    file_path = os.path.join(frontend_path, full_path)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return FileResponse(file_path)
    
    index_file = os.path.join(frontend_path, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    
    return {"status": "ok", "message": "Backend API is running. Frontend build folder not found in container."}
