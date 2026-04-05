"""QuotedBy — Pydantic schemas."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Available AI models
# ---------------------------------------------------------------------------

AVAILABLE_MODELS: list[dict[str, str]] = [
    {"id": "qwen/qwen3-30b-a3b:free", "name": "Qwen 3 30B", "provider": "Alibaba"},
    {"id": "google/gemini-2.0-flash-001", "name": "Gemini 2.0 Flash", "provider": "Google"},
    {"id": "nvidia/nemotron-3-super-120b-a12b:free", "name": "Nemotron 120B", "provider": "NVIDIA"},
    {"id": "stepfun/step-3.5-flash:free", "name": "Step 3.5 Flash", "provider": "StepFun"},
    {"id": "minimax/minimax-m2.5:free", "name": "MiniMax M2.5", "provider": "MiniMax"},
    {"id": "deepseek/deepseek-chat-v3-0324:free", "name": "DeepSeek V3", "provider": "DeepSeek"},
    {"id": "meta-llama/llama-4-maverick:free", "name": "Llama 4 Maverick", "provider": "Meta"},
    {"id": "microsoft/phi-4:free", "name": "Phi 4", "provider": "Microsoft"},
]

_MODEL_NAME_MAP: dict[str, str] = {m["id"]: m["name"] for m in AVAILABLE_MODELS}
_VALID_MODEL_IDS: set[str] = {m["id"] for m in AVAILABLE_MODELS}

DEFAULT_MODEL_IDS: list[str] = [
    "qwen/qwen3-30b-a3b:free",
    "google/gemini-2.0-flash-001",
    "nvidia/nemotron-3-super-120b-a12b:free",
]


def model_display_name(model_id: str) -> str:
    """Extract display name from model_id via lookup or parsing."""
    if model_id in _MODEL_NAME_MAP:
        return _MODEL_NAME_MAP[model_id]
    # Fallback: parse "provider/name:tag" -> "Name"
    name_part = model_id.split("/")[-1] if "/" in model_id else model_id
    name_part = name_part.split(":")[0]
    return name_part.replace("-", " ").title()


# ---------------------------------------------------------------------------
# Project schemas
# ---------------------------------------------------------------------------

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Product/brand name")
    category: str = Field(..., min_length=1, max_length=200, description="Product category")
    competitors: list[str] = Field(default_factory=list, description="Competitor names")
    queries: list[str] = Field(default_factory=list, description="Search queries to track")
    url: Optional[str] = Field(None, description="Product website URL")

    @field_validator("name", "category")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()

    @field_validator("competitors", "queries")
    @classmethod
    def strip_list_items(cls, v: list[str]) -> list[str]:
        return [s.strip() for s in v if s.strip()]


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    competitors: Optional[list[str]] = None
    queries: Optional[list[str]] = None
    url: Optional[str] = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    category: str
    competitors: list[str]
    queries: list[str]
    url: Optional[str]
    created_at: str


# ---------------------------------------------------------------------------
# Scan schemas
# ---------------------------------------------------------------------------

class ScanRequest(BaseModel):
    model_ids: list[str] = Field(
        default=DEFAULT_MODEL_IDS,
        description="OpenRouter model IDs to scan",
    )

    @field_validator("model_ids")
    @classmethod
    def validate_model_ids(cls, v: list[str]) -> list[str]:
        if not v:
            return DEFAULT_MODEL_IDS
        return v


class ScanResult(BaseModel):
    query: str
    model: str
    mentioned: bool
    position: Optional[int] = None
    context: Optional[str] = None
    competitors_mentioned: list[str] = Field(default_factory=list)
    scanned_at: str


class ScanResponse(BaseModel):
    project_id: int
    scanned_queries: int
    scanned_models: int
    total_checks: int
    mentions_found: int
    mention_rate_pct: float
    results: list[ScanResult]


# ---------------------------------------------------------------------------
# Dashboard schemas
# ---------------------------------------------------------------------------

class ModelVisibility(BaseModel):
    model: str
    mentioned_count: int
    total_queries: int
    visibility_pct: float
    avg_position: Optional[float] = None


class CompetitorScore(BaseModel):
    name: str
    mentioned_count: int
    total_queries: int
    visibility_pct: float
    avg_position: Optional[float] = None


class DashboardResponse(BaseModel):
    project_id: int
    project_name: str
    visibility_score: int
    total_queries: int
    total_mentions: int
    mention_rate_pct: float
    by_model: list[ModelVisibility]
    competitors: list[CompetitorScore]
    recent_scans: list[ScanResult]
    recommendations: list[str]


class TrendEntry(BaseModel):
    date: str
    visibility_score: int
    mention_rate_pct: float


# ---------------------------------------------------------------------------
# Defamation schemas
# ---------------------------------------------------------------------------

class DefamationResult(BaseModel):
    id: int
    project_id: int
    model: str
    query: str
    claim: str | None = None
    severity: str
    type: str
    response_text: str
    checked_at: str


class DefamationResponse(BaseModel):
    project_id: int
    total_checks: int
    critical: int
    warnings: int
    clean: int
    results: list[dict]


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    version: str
