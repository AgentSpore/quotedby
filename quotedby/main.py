"""QuotedBy — AI Citation Checker.

Monitor if AI models mention your product. GEO/AEO analytics.
"""
from __future__ import annotations

import os
import pathlib
from contextlib import asynccontextmanager

import aiosqlite
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from quotedby.database import DB_PATH, init_db
from quotedby.schemas.models import HealthResponse
from quotedby.api.projects import router as projects_router
from quotedby.api.scans import router as scans_router
from quotedby.api.models import router as models_router

STATIC_DIR = pathlib.Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting QuotedBy v2.0.0, DB={}", DB_PATH)
    app.state.db = await aiosqlite.connect(DB_PATH)
    await init_db(app.state.db)
    yield
    await app.state.db.close()
    logger.info("QuotedBy shutdown")


app = FastAPI(
    title="QuotedBy",
    description=(
        "AI Citation Checker — monitor if ChatGPT, Perplexity, Gemini, Claude "
        "mention your product. Track visibility score, benchmark vs competitors."
    ),
    version="2.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
async def health():
    return {"status": "ok", "version": "2.0.0"}


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(projects_router)
app.include_router(scans_router)
app.include_router(models_router)


# ---------------------------------------------------------------------------
# Static UI
# ---------------------------------------------------------------------------

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
async def index():
    html = STATIC_DIR / "index.html"
    if html.exists():
        return FileResponse(str(html))
    return {"message": "QuotedBy API — see /docs"}
