"""QuotedBy — Pydantic models."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class AIModel(str, Enum):
    chatgpt = "chatgpt"
    perplexity = "perplexity"
    gemini = "gemini"


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Product/brand name")
    category: str = Field(..., min_length=1, max_length=200, description="Product category, e.g. 'fake review detector'")
    competitors: list[str] = Field(default_factory=list, description="Competitor names")
    queries: list[str] = Field(default_factory=list, description="Search queries to track")
    url: Optional[str] = Field(None, description="Product website URL")


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


class ScanResult(BaseModel):
    query: str
    model: str
    mentioned: bool
    position: Optional[int] = None
    context: Optional[str] = None
    competitors_mentioned: list[str] = Field(default_factory=list)
    scanned_at: str


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


class ScanRequest(BaseModel):
    models: list[AIModel] = Field(
        default=[AIModel.chatgpt, AIModel.perplexity, AIModel.gemini],
        description="Which AI models to scan"
    )


class TrendEntry(BaseModel):
    date: str
    visibility_score: int
    mention_rate_pct: float


class HealthResponse(BaseModel):
    status: str
    version: str
