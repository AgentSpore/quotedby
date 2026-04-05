"""QuotedBy — Project CRUD routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from quotedby.schemas.models import (
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    ScanResult,
    TrendEntry,
)
from quotedby.services import project_service

router = APIRouter(tags=["projects"])


def _get_db(request: Request):
    return request.app.state.db


@router.post("/projects", response_model=ProjectResponse, status_code=201)
async def create(request: Request, body: ProjectCreate):
    data = body.model_dump()
    return await project_service.create_project(_get_db(request), data)


@router.get("/projects", response_model=list[ProjectResponse])
async def list_all(request: Request):
    return await project_service.list_projects(_get_db(request))


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_one(request: Request, project_id: int):
    proj = await project_service.get_project(_get_db(request), project_id)
    if not proj:
        raise HTTPException(404, "Project not found")
    return proj


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
async def update(request: Request, project_id: int, body: ProjectUpdate):
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    proj = await project_service.update_project(_get_db(request), project_id, data)
    if not proj:
        raise HTTPException(404, "Project not found")
    return proj


@router.delete("/projects/{project_id}")
async def delete(request: Request, project_id: int):
    ok = await project_service.delete_project(_get_db(request), project_id)
    if not ok:
        raise HTTPException(404, "Project not found")
    return {"status": "deleted"}


@router.get("/projects/{project_id}/dashboard")
async def dashboard(request: Request, project_id: int):
    data = await project_service.get_dashboard(_get_db(request), project_id)
    if data is None:
        raise HTTPException(404, "Project not found")
    return data


@router.get("/projects/{project_id}/trends", response_model=list[TrendEntry])
async def trends(
    request: Request, project_id: int, days: int = Query(30, ge=1, le=365),
):
    proj = await project_service.get_project(_get_db(request), project_id)
    if not proj:
        raise HTTPException(404, "Project not found")
    return await project_service.get_trends(_get_db(request), project_id, days=days)
