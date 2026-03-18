"""QuotedBy — AI Citation Checker.

Monitor if AI models mention your product. GEO/AEO analytics.
"""
from __future__ import annotations

import os
import pathlib
from contextlib import asynccontextmanager

import aiosqlite
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from models import (
    ProjectCreate, ProjectUpdate, ProjectResponse,
    ScanRequest, DashboardResponse, TrendEntry,
    ScanResult, HealthResponse,
)
from engine import (
    init_db, create_project, list_projects, get_project,
    update_project, delete_project, save_scan, get_scans,
    get_dashboard, get_trends,
)
from scanner import scan_project, generate_queries

DB_PATH = os.environ.get("DB_PATH", "quotedby.db")
STATIC_DIR = pathlib.Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = await aiosqlite.connect(DB_PATH)
    await init_db(app.state.db)
    yield
    await app.state.db.close()


app = FastAPI(
    title="QuotedBy",
    description=(
        "AI Citation Checker — monitor if ChatGPT, Perplexity, Gemini, Claude "
        "mention your product. Track visibility score, benchmark vs competitors."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
async def health():
    return {"status": "ok", "version": "1.0.0"}


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

@app.post("/projects", response_model=ProjectResponse, status_code=201)
async def create(body: ProjectCreate):
    data = body.model_dump()
    # Auto-generate queries if none provided
    if not data.get("queries"):
        data["queries"] = generate_queries(data["name"], data["category"], count=8)
    return await create_project(app.state.db, data)


@app.get("/projects", response_model=list[ProjectResponse])
async def list_all():
    return await list_projects(app.state.db)


@app.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_one(project_id: int):
    proj = await get_project(app.state.db, project_id)
    if not proj:
        raise HTTPException(404, "Project not found")
    return proj


@app.patch("/projects/{project_id}", response_model=ProjectResponse)
async def update(project_id: int, body: ProjectUpdate):
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    proj = await update_project(app.state.db, project_id, data)
    if not proj:
        raise HTTPException(404, "Project not found")
    return proj


@app.delete("/projects/{project_id}")
async def delete(project_id: int):
    ok = await delete_project(app.state.db, project_id)
    if not ok:
        raise HTTPException(404, "Project not found")
    return {"status": "deleted"}


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------

@app.post("/projects/{project_id}/scan")
async def scan(project_id: int, body: ScanRequest | None = None):
    """Run a scan across AI models for this project."""
    proj = await get_project(app.state.db, project_id)
    if not proj:
        raise HTTPException(404, "Project not found")

    if not proj.get("queries"):
        raise HTTPException(422, "No queries defined. Add queries to the project first.")

    models = [m.value for m in body.models] if body else ["chatgpt", "perplexity", "gemini", "claude"]
    results = await scan_project(proj, models=models)

    # Save results
    saved = []
    for r in results:
        await save_scan(app.state.db, project_id, r)
        saved.append({
            "query": r["query"], "model": r["model"],
            "mentioned": r["mentioned"], "position": r.get("position"),
            "context": r.get("context"),
            "competitors_mentioned": r.get("competitors_mentioned", []),
            "scanned_at": r["scanned_at"],
        })

    mentioned = sum(1 for r in results if r["mentioned"])
    return {
        "project_id": project_id,
        "scanned_queries": len(proj["queries"]),
        "scanned_models": len(models),
        "total_checks": len(results),
        "mentions_found": mentioned,
        "mention_rate_pct": round(mentioned / len(results) * 100, 1) if results else 0,
        "results": saved,
    }


@app.get("/projects/{project_id}/results", response_model=list[ScanResult])
async def results(project_id: int, limit: int = Query(50, ge=1, le=500)):
    proj = await get_project(app.state.db, project_id)
    if not proj:
        raise HTTPException(404, "Project not found")
    scans = await get_scans(app.state.db, project_id, limit=limit)
    return scans


# ---------------------------------------------------------------------------
# Dashboard & Trends
# ---------------------------------------------------------------------------

@app.get("/projects/{project_id}/dashboard")
async def dashboard(project_id: int):
    data = await get_dashboard(app.state.db, project_id)
    if data is None:
        raise HTTPException(404, "Project not found")
    return data


@app.get("/projects/{project_id}/trends", response_model=list[TrendEntry])
async def trends(project_id: int, days: int = Query(30, ge=1, le=365)):
    proj = await get_project(app.state.db, project_id)
    if not proj:
        raise HTTPException(404, "Project not found")
    return await get_trends(app.state.db, project_id, days=days)


# ---------------------------------------------------------------------------
# Query suggestions
# ---------------------------------------------------------------------------

@app.get("/suggest-queries")
async def suggest_queries(
    name: str = Query(..., description="Product name"),
    category: str = Query(..., description="Product category"),
    count: int = Query(10, ge=1, le=20),
):
    return {"queries": generate_queries(name, category, count=count)}


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
