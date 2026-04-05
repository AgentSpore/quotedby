"""QuotedBy — Defamation check service."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from loguru import logger

from quotedby.schemas.models import DEFAULT_MODEL_IDS, model_display_name
from quotedby.services.scan_service import _call_openrouter


def _build_defamation_queries(product_name: str) -> list[str]:
    return [
        f"Tell me about {product_name}. What is it and is it any good?",
        f"Is {product_name} a scam or legitimate?",
        f"What are the alternatives to {product_name}?",
    ]


def _build_analysis_prompt(
    product_name: str,
    category: str,
    known_facts: list[str],
    query: str,
    response_text: str,
) -> str:
    facts_str = "\n".join(f"- {f}" for f in known_facts) if known_facts else "- No known facts provided"
    return (
        f'You are an AI output auditor. A user asked an AI model: "{query}"\n\n'
        f"The AI responded:\n---\n{response_text}\n---\n\n"
        f'The product being checked is "{product_name}" in the "{category}" category.\n'
        f"Known facts about the product:\n{facts_str}\n\n"
        f"Analyze the AI response for:\n"
        f"1. FALSE CLAIMS - product is closed/discontinued/scam/doesn't exist when it does\n"
        f"2. OUTDATED INFO - old pricing, old features, old versions\n"
        f"3. COMPETITOR CONFUSION - mixing up with another product\n"
        f"4. NEGATIVE BIAS - negative statements without evidence\n\n"
        f"Respond in JSON format. If no issues found, return:\n"
        f'{{"findings": []}}\n\n'
        f"If issues found, return:\n"
        f'{{"findings": [{{"claim": "exact problematic claim from the response",'
        f'"severity": "critical|warning|info",'
        f'"type": "false_claim|outdated_info|competitor_confusion|negative_bias"}}]}}\n\n'
        f"Only return the JSON, nothing else."
    )


async def defamation_scan(
    product_name: str,
    category: str,
    known_facts: list[str] | None = None,
    model_ids: list[str] | None = None,
) -> list[dict]:
    """Ask AI models about the brand, then analyze responses for false/harmful claims."""
    if model_ids is None:
        model_ids = DEFAULT_MODEL_IDS
    if known_facts is None:
        known_facts = []

    queries = _build_defamation_queries(product_name)
    results: list[dict] = []
    now_str = datetime.now(timezone.utc).isoformat()

    for query in queries:
        for model_id in model_ids:
            display_name = model_display_name(model_id)
            response_text = await asyncio.to_thread(_call_openrouter, model_id, query)

            if response_text is None:
                results.append({
                    "model": display_name,
                    "query": query,
                    "claim": None,
                    "severity": "info",
                    "type": "clean",
                    "response_text": "API unavailable",
                    "checked_at": now_str,
                })
                continue

            # Analyze the response for defamatory content
            analysis_prompt = _build_analysis_prompt(
                product_name, category, known_facts, query, response_text,
            )
            # Use first available model for analysis
            analysis_model = model_ids[0]
            analysis_text = await asyncio.to_thread(
                _call_openrouter, analysis_model, analysis_prompt,
            )

            findings = []
            if analysis_text:
                try:
                    cleaned = analysis_text.strip()
                    if cleaned.startswith("```"):
                        cleaned = "\n".join(cleaned.split("\n")[1:])
                        if cleaned.endswith("```"):
                            cleaned = cleaned[:-3]
                        cleaned = cleaned.strip()
                    parsed = json.loads(cleaned)
                    findings = parsed.get("findings", [])
                except (json.JSONDecodeError, KeyError):
                    logger.warning("Failed to parse analysis response for model={}", display_name)

            if findings:
                for f in findings:
                    results.append({
                        "model": display_name,
                        "query": query,
                        "claim": f.get("claim"),
                        "severity": f.get("severity", "warning"),
                        "type": f.get("type", "negative_bias"),
                        "response_text": response_text,
                        "checked_at": now_str,
                    })
            else:
                results.append({
                    "model": display_name,
                    "query": query,
                    "claim": None,
                    "severity": "clean",
                    "type": "clean",
                    "response_text": response_text,
                    "checked_at": now_str,
                })

    logger.info(
        "Defamation scan complete: product={}, {} results", product_name, len(results),
    )
    return results
