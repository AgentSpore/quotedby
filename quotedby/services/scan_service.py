"""QuotedBy — Scan service (AI model querying via OpenRouter)."""
from __future__ import annotations

import asyncio
import json
import os
import re
import urllib.request
from datetime import datetime, timezone
from typing import Optional

from loguru import logger

from quotedby.schemas.models import model_display_name

OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")


def _build_prompt(query: str, product_name: str, category: str) -> str:
    return (
        f"User question: {query}\n\n"
        f"Please answer this question helpfully. Recommend specific tools or products by name "
        f"if you know good ones in the '{category}' category. "
        f"Be specific with product names."
    )


def _call_openrouter(model_id: str, prompt: str, timeout: int = 30) -> Optional[str]:
    """Call OpenRouter API and return response text."""
    if not OPENROUTER_KEY:
        return None

    data = json.dumps({
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1000,
    }).encode()

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=data,
        headers={
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "QuotedBy/2.0",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read())
        return result["choices"][0]["message"]["content"]
    except Exception:
        logger.warning("OpenRouter call failed for model={}", model_id)
        return None


def _parse_mentions(
    response_text: str,
    product_name: str,
    competitors: list[str],
) -> dict:
    """Parse AI response to find product and competitor mentions."""
    text_lower = response_text.lower()
    product_lower = product_name.lower()

    mentioned = product_lower in text_lower

    position = None
    if mentioned:
        lines = response_text.split("\n")
        for i, line in enumerate(lines):
            if product_lower in line.lower():
                m = re.match(r"^\s*(\d+)[.)]\s", line)
                if m:
                    position = int(m.group(1))
                else:
                    position = i + 1
                break

    context = None
    if mentioned:
        idx = text_lower.find(product_lower)
        start = max(0, idx - 80)
        end = min(len(response_text), idx + len(product_name) + 120)
        context = response_text[start:end].strip()

    competitors_mentioned = [c for c in competitors if c.lower() in text_lower]

    return {
        "mentioned": mentioned,
        "position": position,
        "context": context,
        "competitors_mentioned": competitors_mentioned,
    }


async def scan_query(
    query: str,
    model_id: str,
    product_name: str,
    category: str,
    competitors: list[str],
) -> dict:
    """Scan a single query against a single model (by model_id)."""
    prompt = _build_prompt(query, product_name, category)
    display_name = model_display_name(model_id)

    response_text = await asyncio.to_thread(_call_openrouter, model_id, prompt)

    if response_text is None:
        return {
            "query": query,
            "model": display_name,
            "mentioned": False,
            "position": None,
            "context": None,
            "competitors_mentioned": [],
            "response_text": None,
            "scanned_at": datetime.now(timezone.utc).isoformat(),
            "error": "API unavailable — set OPENROUTER_API_KEY",
        }

    parsed = _parse_mentions(response_text, product_name, competitors)

    return {
        "query": query,
        "model": display_name,
        "mentioned": parsed["mentioned"],
        "position": parsed["position"],
        "context": parsed["context"],
        "competitors_mentioned": parsed["competitors_mentioned"],
        "response_text": response_text,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
    }


async def scan_project(
    project: dict,
    model_ids: list[str],
) -> list[dict]:
    """Scan all queries for a project across specified model IDs (parallel)."""
    queries = project.get("queries", [])
    if not queries:
        return []

    tasks = []
    for query in queries:
        for mid in model_ids:
            tasks.append(
                scan_query(
                    query=query,
                    model_id=mid,
                    product_name=project["name"],
                    category=project["category"],
                    competitors=project.get("competitors", []),
                )
            )

    logger.info(
        "Scanning project={} with {} queries x {} models = {} tasks",
        project["name"], len(queries), len(model_ids), len(tasks),
    )

    results = await asyncio.gather(*tasks, return_exceptions=True)
    clean = []
    for r in results:
        if isinstance(r, Exception):
            logger.error("Scan task failed: {}", r)
            continue
        clean.append(r)

    return clean
