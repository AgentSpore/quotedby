"""QuotedBy — Multi-model AI scanner.

Queries AI models and checks if a product is mentioned in responses.
Uses OpenRouter for unified access to multiple models.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from datetime import datetime, timezone
from typing import Optional


OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")

# Model mapping: our name -> OpenRouter model ID
MODEL_MAP = {
    "chatgpt": "google/gemini-2.0-flash-001",  # free
    "perplexity": "google/gemini-2.0-flash-001",  # free
    "gemini": "google/gemini-2.0-flash-001",    # free
}

# Fallbacks if primary model fails
FREE_MODELS = {
    "chatgpt": "google/gemini-2.0-flash-001",
    "perplexity": "google/gemini-2.0-flash-001",
    "gemini": "google/gemini-2.0-flash-001",
}


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
            "User-Agent": "QuotedBy/1.0",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read())
        return result["choices"][0]["message"]["content"]
    except Exception:
        return None


def _parse_mentions(
    response_text: str,
    product_name: str,
    competitors: list[str],
) -> dict:
    """Parse AI response to find product and competitor mentions."""
    text_lower = response_text.lower()
    product_lower = product_name.lower()

    # Check if product is mentioned
    mentioned = product_lower in text_lower

    # Find position (which recommendation number)
    position = None
    if mentioned:
        # Try numbered list pattern: "1. ProductName" or "**ProductName**"
        lines = response_text.split("\n")
        for i, line in enumerate(lines):
            if product_lower in line.lower():
                # Check for numbered position
                m = re.match(r"^\s*(\d+)[.)]\s", line)
                if m:
                    position = int(m.group(1))
                else:
                    position = i + 1
                break

    # Extract context around mention
    context = None
    if mentioned:
        idx = text_lower.find(product_lower)
        start = max(0, idx - 80)
        end = min(len(response_text), idx + len(product_name) + 120)
        context = response_text[start:end].strip()

    # Check competitors
    competitors_mentioned = [
        c for c in competitors
        if c.lower() in text_lower
    ]

    return {
        "mentioned": mentioned,
        "position": position,
        "context": context,
        "competitors_mentioned": competitors_mentioned,
    }


async def scan_query(
    query: str,
    model_name: str,
    product_name: str,
    category: str,
    competitors: list[str],
) -> dict:
    """Scan a single query against a single model."""
    prompt = _build_prompt(query, product_name, category)

    import asyncio

    # Try primary model, then free fallback (run blocking IO in thread)
    model_id = MODEL_MAP.get(model_name, MODEL_MAP["chatgpt"])
    response_text = await asyncio.to_thread(_call_openrouter, model_id, prompt)

    if response_text is None:
        # Try free fallback
        fallback_id = FREE_MODELS.get(model_name)
        if fallback_id:
            response_text = await asyncio.to_thread(_call_openrouter, fallback_id, prompt)

    if response_text is None:
        # No API key or all models failed — return empty result
        return {
            "query": query,
            "model": model_name,
            "mentioned": False,
            "position": None,
            "context": None,
            "competitors_mentioned": [],
            "response_text": None,
            "scanned_at": datetime.now(timezone.utc).isoformat(),
            "error": "API unavailable — set OPENROUTER_API_KEY",
        }

    # Parse response
    parsed = _parse_mentions(response_text, product_name, competitors)

    return {
        "query": query,
        "model": model_name,
        "mentioned": parsed["mentioned"],
        "position": parsed["position"],
        "context": parsed["context"],
        "competitors_mentioned": parsed["competitors_mentioned"],
        "response_text": response_text,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
    }


async def scan_project(
    project: dict,
    models: list[str] | None = None,
) -> list[dict]:
    """Scan all queries for a project across specified models (parallel)."""
    import asyncio

    if models is None:
        models = ["chatgpt", "perplexity", "gemini"]

    queries = project.get("queries", [])
    if not queries:
        return []

    # Build all tasks and run in parallel
    tasks = []
    for query in queries:
        for model_name in models:
            tasks.append(scan_query(
                query=query,
                model_name=model_name,
                product_name=project["name"],
                category=project["category"],
                competitors=project.get("competitors", []),
            ))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    # Filter out exceptions
    clean = []
    for r in results:
        if isinstance(r, Exception):
            continue
        clean.append(r)

    return clean


def generate_queries(product_name: str, category: str, count: int = 10) -> list[str]:
    """Generate relevant search queries for a product category."""
    templates = [
        f"What is the best {category} tool in 2026?",
        f"Best {category} for small business",
        f"Top {category} tools compared",
        f"{category} software recommendations",
        f"Free {category} tools",
        f"Best alternative to popular {category}",
        f"How to choose a {category}",
        f"What {category} do you recommend?",
        f"Best {category} for startups",
        f"{product_name} vs competitors — which is better?",
        f"Is {product_name} good for {category}?",
        f"Most recommended {category} on Reddit",
    ]
    return templates[:count]
