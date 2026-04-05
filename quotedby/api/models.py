"""QuotedBy — Available models route."""
from __future__ import annotations

import json
import urllib.request

from fastapi import APIRouter, Query
from loguru import logger

from quotedby.schemas.models import AVAILABLE_MODELS
from quotedby.services.project_service import generate_queries

router = APIRouter(tags=["models"])

_CACHED_MODELS: list[dict] | None = None


def _fetch_free_models() -> list[dict]:
    """Fetch all free models from OpenRouter API, with fallback to hardcoded list."""
    global _CACHED_MODELS
    if _CACHED_MODELS is not None:
        return _CACHED_MODELS

    try:
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/models",
            headers={"User-Agent": "QuotedBy/2.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())

        models = data.get("data", [])
        free = [
            {
                "id": m["id"],
                "name": m.get("name", m["id"]),
                "context_length": m.get("context_length", 0),
                "provider": m["id"].split("/")[0].capitalize() if "/" in m["id"] else "",
            }
            for m in models
            if ":free" in m.get("id", "")
        ]
        _CACHED_MODELS = sorted(free, key=lambda x: x["name"])
        logger.info("Loaded {} free models from OpenRouter", len(_CACHED_MODELS))
        return _CACHED_MODELS
    except Exception as e:
        logger.warning("Failed to fetch models from OpenRouter: {}", e)
        return AVAILABLE_MODELS


@router.get("/models")
async def get_available_models():
    """Return list of available free AI models (loaded dynamically from OpenRouter)."""
    return _fetch_free_models()


@router.get("/models/refresh")
async def refresh_models():
    """Force refresh model list from OpenRouter."""
    global _CACHED_MODELS
    _CACHED_MODELS = None
    models = _fetch_free_models()
    return {"count": len(models), "models": models}


@router.get("/suggest-queries")
async def suggest_queries(
    name: str = Query(..., description="Product name"),
    category: str = Query(..., description="Product category"),
    count: int = Query(10, ge=1, le=20),
):
    """Generate query suggestions for a product."""
    return {"queries": generate_queries(name, category, count=count)}
