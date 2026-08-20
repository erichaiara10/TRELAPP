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

from core.db import client
from routes import (
    ai, auth, content, csv_io, customers, files, inspections, leads, locations,
    market, matching, properties, property_types, public, referrals, reports, requirements, tasks,
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
    ai, content, reports, public, referrals, market, files, csv_io,
):
    api.include_router(module.router)


@api.get("/")
async def root():
    return {"ok": True, "service": "TREL API"}


@app.on_event("startup")
async def on_startup():
    files.init_storage()
    await run_startup()
    try:
        hello = await client.admin.command("hello")
        replica_set = hello.get("setName")
        mode = "REPLICA_SET" if replica_set else ("SHARDED" if hello.get("msg") == "isdbgrid" else "STANDALONE")
        logger.info("MongoDB topology: %s (transactions %s)", mode, "enabled" if mode != "STANDALONE" else "disabled — using non-transactional fallback")
    except Exception as exc:
        logger.warning("Unable to detect MongoDB topology: %s", exc)


@app.on_event("shutdown")
async def shutdown():
    client.close()


app.include_router(api)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=False,
    allow_methods=["*"], allow_headers=["*"],
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
