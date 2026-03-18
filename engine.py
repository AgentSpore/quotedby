"""QuotedBy — DB engine (aiosqlite)."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import aiosqlite


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def init_db(db: aiosqlite.Connection) -> None:
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            competitors TEXT NOT NULL DEFAULT '[]',
            queries TEXT NOT NULL DEFAULT '[]',
            url TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES projects(id),
            query TEXT NOT NULL,
            model TEXT NOT NULL,
            mentioned INTEGER NOT NULL DEFAULT 0,
            position INTEGER,
            context TEXT,
            competitors_mentioned TEXT NOT NULL DEFAULT '[]',
            response_text TEXT,
            scanned_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_scans_project ON scans(project_id);
        CREATE INDEX IF NOT EXISTS idx_scans_date ON scans(scanned_at);
    """)
    await db.commit()


# --- Projects ---

async def create_project(db: aiosqlite.Connection, data: dict) -> dict:
    now = _now()
    cur = await db.execute(
        "INSERT INTO projects (name, category, competitors, queries, url, created_at) VALUES (?,?,?,?,?,?)",
        (data["name"], data["category"],
         json.dumps(data.get("competitors", [])),
         json.dumps(data.get("queries", [])),
         data.get("url"), now),
    )
    await db.commit()
    return {**data, "id": cur.lastrowid, "created_at": now,
            "competitors": data.get("competitors", []),
            "queries": data.get("queries", [])}


async def list_projects(db: aiosqlite.Connection) -> list[dict]:
    cur = await db.execute("SELECT * FROM projects ORDER BY created_at DESC")
    rows = await cur.fetchall()
    result = []
    for r in rows:
        result.append({
            "id": r[0], "name": r[1], "category": r[2],
            "competitors": json.loads(r[3]), "queries": json.loads(r[4]),
            "url": r[5], "created_at": r[6],
        })
    return result


async def get_project(db: aiosqlite.Connection, project_id: int) -> dict | None:
    cur = await db.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    r = await cur.fetchone()
    if not r:
        return None
    return {
        "id": r[0], "name": r[1], "category": r[2],
        "competitors": json.loads(r[3]), "queries": json.loads(r[4]),
        "url": r[5], "created_at": r[6],
    }


async def update_project(db: aiosqlite.Connection, project_id: int, data: dict) -> dict | None:
    proj = await get_project(db, project_id)
    if not proj:
        return None
    name = data.get("name", proj["name"])
    category = data.get("category", proj["category"])
    competitors = json.dumps(data["competitors"]) if "competitors" in data else json.dumps(proj["competitors"])
    queries = json.dumps(data["queries"]) if "queries" in data else json.dumps(proj["queries"])
    url = data.get("url", proj["url"])
    await db.execute(
        "UPDATE projects SET name=?, category=?, competitors=?, queries=?, url=? WHERE id=?",
        (name, category, competitors, queries, url, project_id),
    )
    await db.commit()
    return await get_project(db, project_id)


async def delete_project(db: aiosqlite.Connection, project_id: int) -> bool:
    cur = await db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    await db.execute("DELETE FROM scans WHERE project_id = ?", (project_id,))
    await db.commit()
    return cur.rowcount > 0


# --- Scans ---

async def save_scan(db: aiosqlite.Connection, project_id: int, result: dict) -> int:
    cur = await db.execute(
        """INSERT INTO scans (project_id, query, model, mentioned, position,
           context, competitors_mentioned, response_text, scanned_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (project_id, result["query"], result["model"],
         1 if result["mentioned"] else 0, result.get("position"),
         result.get("context"), json.dumps(result.get("competitors_mentioned", [])),
         result.get("response_text"), result["scanned_at"]),
    )
    await db.commit()
    return cur.lastrowid


async def get_scans(db: aiosqlite.Connection, project_id: int, limit: int = 100) -> list[dict]:
    cur = await db.execute(
        "SELECT * FROM scans WHERE project_id = ? ORDER BY scanned_at DESC LIMIT ?",
        (project_id, limit),
    )
    rows = await cur.fetchall()
    return [
        {
            "id": r[0], "project_id": r[1], "query": r[2], "model": r[3],
            "mentioned": bool(r[4]), "position": r[5], "context": r[6],
            "competitors_mentioned": json.loads(r[7]), "scanned_at": r[9],
        }
        for r in rows
    ]


async def get_dashboard(db: aiosqlite.Connection, project_id: int) -> dict | None:
    proj = await get_project(db, project_id)
    if not proj:
        return None

    scans = await get_scans(db, project_id, limit=500)
    if not scans:
        return {
            "project_id": project_id, "project_name": proj["name"],
            "visibility_score": 0, "total_queries": 0, "total_mentions": 0,
            "mention_rate_pct": 0.0, "by_model": [], "competitors": [],
            "recent_scans": [], "recommendations": _generate_recommendations(proj, [], {}),
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
            "model": m, "mentioned_count": st["mentioned"],
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
    # Add total for competitors not mentioned
    total_scans = len(scans)
    for c in proj.get("competitors", []):
        if c not in comp_stats:
            comp_stats[c] = {"mentioned": 0, "total": total_scans}
        else:
            comp_stats[c]["total"] = total_scans

    competitors = [
        {
            "name": c, "mentioned_count": st["mentioned"],
            "total_queries": st["total"],
            "visibility_pct": round(st["mentioned"] / st["total"] * 100, 1) if st["total"] else 0,
        }
        for c, st in sorted(comp_stats.items(), key=lambda x: -x[1]["mentioned"])
    ]

    # Overall
    total_mentions = sum(1 for s in scans if s["mentioned"])
    mention_rate = round(total_mentions / len(scans) * 100, 1) if scans else 0
    visibility_score = min(100, int(mention_rate * 1.2))  # weighted

    recommendations = _generate_recommendations(proj, scans, model_stats)

    return {
        "project_id": project_id, "project_name": proj["name"],
        "visibility_score": visibility_score,
        "total_queries": len(scans), "total_mentions": total_mentions,
        "mention_rate_pct": mention_rate,
        "by_model": by_model, "competitors": competitors,
        "recent_scans": scans[:20],
        "recommendations": recommendations,
    }


def _generate_recommendations(proj: dict, scans: list, model_stats: dict) -> list[str]:
    recs = []
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

    # Model-specific
    for m, st in model_stats.items():
        rate = st["mentioned"] / st["total"] * 100 if st["total"] else 0
        if rate < 10:
            recs.append(f"Very low visibility on {m}. Research how {m} sources information")

    return recs[:5]


async def get_trends(db: aiosqlite.Connection, project_id: int, days: int = 30) -> list[dict]:
    cur = await db.execute(
        """SELECT DATE(scanned_at) as scan_date,
           SUM(mentioned) as mentions, COUNT(*) as total
           FROM scans WHERE project_id = ?
           GROUP BY DATE(scanned_at)
           ORDER BY scan_date DESC LIMIT ?""",
        (project_id, days),
    )
    rows = await cur.fetchall()
    return [
        {
            "date": r[0],
            "visibility_score": min(100, int(r[1] / r[2] * 120)) if r[2] else 0,
            "mention_rate_pct": round(r[1] / r[2] * 100, 1) if r[2] else 0,
        }
        for r in rows
    ]
