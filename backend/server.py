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

from fastapi import APIRouter, FastAPI
from starlette.middleware.cors import CORSMiddleware

from core.db import client
from routes import (
    ai, auth, content, csv_io, customers, files, inspections, leads, locations,
    market, matching, properties, property_advertising, property_types, public, reports, requirements, tasks,
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
    ai, content, reports, public, files, csv_io, market, property_advertising,
):
    api.include_router(module.router)


@api.get("/")
async def root():
    return {"ok": True, "service": "TREL API"}


@app.on_event("startup")
async def on_startup():
    files.init_storage()
    await run_startup()
    from core.scheduler import start_scheduler
    start_scheduler()


@app.on_event("shutdown")
async def shutdown():
    client.close()


app.include_router(api)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=False,
    allow_methods=["*"], allow_headers=["*"],
)
