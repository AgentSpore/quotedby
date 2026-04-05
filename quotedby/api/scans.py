"""QuotedBy — Scan and defamation routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from quotedby.repositories import defamation_repo, scan_repo
from quotedby.schemas.models import (
    DefamationResult,
    ScanRequest,
    ScanResult,
)
from quotedby.services import project_service, scan_service, defamation_service

router = APIRouter(tags=["scans"])


def _get_db(request: Request):
    return request.app.state.db


@router.post("/projects/{project_id}/scan")
async def scan(request: Request, project_id: int, body: ScanRequest | None = None):
    """Run a scan across AI models for this project."""
    db = _get_db(request)
    proj = await project_service.get_project(db, project_id)
    if not proj:
        raise HTTPException(404, "Project not found")

    if not proj.get("queries"):
        raise HTTPException(422, "No queries defined. Add queries to the project first.")

    model_ids = body.model_ids if body else ScanRequest().model_ids
    results = await scan_service.scan_project(proj, model_ids=model_ids)

    # Save results
    saved = []
    for r in results:
        await scan_repo.save(db, project_id, r)
        saved.append({
            "query": r["query"],
            "model": r["model"],
            "mentioned": r["mentioned"],
            "position": r.get("position"),
            "context": r.get("context"),
            "competitors_mentioned": r.get("competitors_mentioned", []),
            "scanned_at": r["scanned_at"],
        })

    mentioned = sum(1 for r in results if r["mentioned"])
    return {
        "project_id": project_id,
        "scanned_queries": len(proj["queries"]),
        "scanned_models": len(model_ids),
        "total_checks": len(results),
        "mentions_found": mentioned,
        "mention_rate_pct": round(mentioned / len(results) * 100, 1) if results else 0,
        "results": saved,
    }


@router.get("/projects/{project_id}/results", response_model=list[ScanResult])
async def results(
    request: Request, project_id: int, limit: int = Query(50, ge=1, le=500),
):
    db = _get_db(request)
    proj = await project_service.get_project(db, project_id)
    if not proj:
        raise HTTPException(404, "Project not found")
    return await scan_repo.get_by_project(db, project_id, limit=limit)


# ---------------------------------------------------------------------------
# Defamation
# ---------------------------------------------------------------------------

@router.post("/projects/{project_id}/defamation-check")
async def check_defamation(request: Request, project_id: int):
    """Ask AI models about the brand and check for false/harmful claims."""
    db = _get_db(request)
    proj = await project_service.get_project(db, project_id)
    if not proj:
        raise HTTPException(404, "Project not found")

    results = await defamation_service.defamation_scan(
        product_name=proj["name"],
        category=proj["category"],
        known_facts=proj.get("queries", []),
    )

    saved = []
    for r in results:
        row_id = await defamation_repo.save(db, project_id, r)
        saved.append({**r, "id": row_id, "project_id": project_id})

    critical = sum(1 for r in results if r["severity"] == "critical")
    warnings = sum(1 for r in results if r["severity"] == "warning")
    clean = sum(1 for r in results if r["severity"] == "clean")

    return {
        "project_id": project_id,
        "total_checks": len(results),
        "critical": critical,
        "warnings": warnings,
        "clean": clean,
        "results": saved,
    }


@router.get("/projects/{project_id}/defamation", response_model=list[DefamationResult])
async def get_defamation_history(
    request: Request,
    project_id: int,
    limit: int = Query(50, ge=1, le=500),
):
    db = _get_db(request)
    proj = await project_service.get_project(db, project_id)
    if not proj:
        raise HTTPException(404, "Project not found")
    return await defamation_repo.get_by_project(db, project_id, limit=limit)
