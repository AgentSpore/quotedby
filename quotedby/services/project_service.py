"""QuotedBy — Project service (business logic)."""
from __future__ import annotations

import aiosqlite
from loguru import logger

from quotedby.repositories import project_repo, scan_repo


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


async def create_project(db: aiosqlite.Connection, data: dict) -> dict:
    """Create a project, auto-generating queries if needed."""
    if not data.get("queries"):
        data["queries"] = generate_queries(data["name"], data["category"], count=8)
    result = await project_repo.create(db, data)
    logger.info("Project created: id={}, name={}", result["id"], result["name"])
    return result


async def list_projects(db: aiosqlite.Connection) -> list[dict]:
    """Return all projects."""
    return await project_repo.list_all(db)


async def get_project(db: aiosqlite.Connection, project_id: int) -> dict | None:
    """Return a project by ID."""
    return await project_repo.get_by_id(db, project_id)


async def update_project(db: aiosqlite.Connection, project_id: int, data: dict) -> dict | None:
    """Update a project."""
    result = await project_repo.update(db, project_id, data)
    if result:
        logger.info("Project updated: id={}", project_id)
    return result


async def delete_project(db: aiosqlite.Connection, project_id: int) -> bool:
    """Delete a project and all related data."""
    ok = await project_repo.delete(db, project_id)
    if ok:
        logger.info("Project deleted: id={}", project_id)
    return ok


async def get_dashboard(db: aiosqlite.Connection, project_id: int) -> dict | None:
    """Build dashboard data for a project."""
    proj = await project_repo.get_by_id(db, project_id)
    if not proj:
        return None

    scans = await scan_repo.get_by_project(db, project_id, limit=500)
    if not scans:
        return {
            "project_id": project_id,
            "project_name": proj["name"],
            "visibility_score": 0,
            "total_queries": 0,
            "total_mentions": 0,
            "mention_rate_pct": 0.0,
            "by_model": [],
            "competitors": [],
            "recent_scans": [],
            "recommendations": _generate_recommendations(proj, [], {}),
        }

    # By model
    model_stats: dict[str, dict] = {}
    for s in scans:
        m = s["model"]
        if m not in model_stats:
            model_stats[m] = {"mentioned": 0, "total": 0, "positions": []}
        model_stats[m]["total"] += 1
        if s["mentioned"]:
            model_stats[m]["mentioned"] += 1
            if s.get("position"):
                model_stats[m]["positions"].append(s["position"])

    by_model = []
    for m, st in model_stats.items():
        avg_pos = round(sum(st["positions"]) / len(st["positions"]), 1) if st["positions"] else None
        by_model.append({
            "model": m,
            "mentioned_count": st["mentioned"],
            "total_queries": st["total"],
            "visibility_pct": round(st["mentioned"] / st["total"] * 100, 1) if st["total"] else 0,
            "avg_position": avg_pos,
        })

    # Competitors
    comp_stats: dict[str, dict] = {}
    for s in scans:
        for c in s.get("competitors_mentioned", []):
            if c not in comp_stats:
                comp_stats[c] = {"mentioned": 0, "total": 0}
            comp_stats[c]["total"] += 1
            comp_stats[c]["mentioned"] += 1

    total_scans = len(scans)
    for c in proj.get("competitors", []):
        if c not in comp_stats:
            comp_stats[c] = {"mentioned": 0, "total": total_scans}
        else:
            comp_stats[c]["total"] = total_scans

    competitors = [
        {
            "name": c,
            "mentioned_count": st["mentioned"],
            "total_queries": st["total"],
            "visibility_pct": round(st["mentioned"] / st["total"] * 100, 1) if st["total"] else 0,
        }
        for c, st in sorted(comp_stats.items(), key=lambda x: -x[1]["mentioned"])
    ]

    total_mentions = sum(1 for s in scans if s["mentioned"])
    mention_rate = round(total_mentions / len(scans) * 100, 1) if scans else 0
    visibility_score = min(100, int(mention_rate * 1.2))

    recommendations = _generate_recommendations(proj, scans, model_stats)

    return {
        "project_id": project_id,
        "project_name": proj["name"],
        "visibility_score": visibility_score,
        "total_queries": len(scans),
        "total_mentions": total_mentions,
        "mention_rate_pct": mention_rate,
        "by_model": by_model,
        "competitors": competitors,
        "recent_scans": scans[:20],
        "recommendations": recommendations,
    }


def _generate_recommendations(proj: dict, scans: list, model_stats: dict) -> list[str]:
    """Generate actionable recommendations based on scan data."""
    recs: list[str] = []
    if not scans:
        recs.append(f"Run your first scan to see how AI models perceive '{proj['name']}'")
        if not proj.get("queries"):
            recs.append("Add search queries that your target customers would ask AI assistants")
        if not proj.get("competitors"):
            recs.append("Add competitor names to benchmark your visibility against them")
        return recs

    total_mentions = sum(1 for s in scans if s["mentioned"])
    mention_rate = total_mentions / len(scans) * 100 if scans else 0

    if mention_rate < 20:
        recs.append("Low visibility! Create comparison pages (vs competitors) — AI models heavily cite these")
        recs.append("Publish 'best [category] tools 2026' content on your blog")
        recs.append("Get mentioned on 3+ third-party review/listicle sites")
    elif mention_rate < 50:
        recs.append("Growing visibility. Add structured data (schema.org) to improve AI parsing")
        recs.append("Create a detailed FAQ page — AI models love extracting from FAQ content")
    else:
        recs.append("Strong visibility! Monitor weekly to maintain position")

    for m, st in model_stats.items():
        rate = st["mentioned"] / st["total"] * 100 if st["total"] else 0
        if rate < 10:
            recs.append(f"Very low visibility on {m}. Research how {m} sources information")

    return recs[:5]


async def get_trends(db: aiosqlite.Connection, project_id: int, days: int = 30) -> list[dict]:
    """Return daily visibility trends."""
    return await scan_repo.get_trends(db, project_id, days=days)
