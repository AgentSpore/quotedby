"""QuotedBy — Scan repository (DB operations)."""
from __future__ import annotations

import json

import aiosqlite


async def save(db: aiosqlite.Connection, project_id: int, result: dict) -> int:
    """Insert a scan result and return its ID."""
    cur = await db.execute(
        """INSERT INTO scans
           (project_id, query, model, mentioned, position,
            context, competitors_mentioned, response_text, scanned_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (
            project_id,
            result["query"],
            result["model"],
            1 if result["mentioned"] else 0,
            result.get("position"),
            result.get("context"),
            json.dumps(result.get("competitors_mentioned", [])),
            result.get("response_text"),
            result["scanned_at"],
        ),
    )
    await db.commit()
    return cur.lastrowid


async def get_by_project(
    db: aiosqlite.Connection, project_id: int, limit: int = 100,
) -> list[dict]:
    """Return scans for a project ordered by date desc."""
    cur = await db.execute(
        "SELECT * FROM scans WHERE project_id = ? ORDER BY scanned_at DESC LIMIT ?",
        (project_id, limit),
    )
    rows = await cur.fetchall()
    return [
        {
            "id": r[0],
            "project_id": r[1],
            "query": r[2],
            "model": r[3],
            "mentioned": bool(r[4]),
            "position": r[5],
            "context": r[6],
            "competitors_mentioned": json.loads(r[7]),
            "scanned_at": r[9],
        }
        for r in rows
    ]


async def get_trends(
    db: aiosqlite.Connection, project_id: int, days: int = 30,
) -> list[dict]:
    """Return daily aggregated scan data."""
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
