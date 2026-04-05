"""QuotedBy — Defamation repository (DB operations)."""
from __future__ import annotations

import aiosqlite


async def save(db: aiosqlite.Connection, project_id: int, result: dict) -> int:
    """Insert a defamation check result and return its ID."""
    cur = await db.execute(
        """INSERT INTO defamation_checks
           (project_id, model, query, claim, severity, type, response_text, checked_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (
            project_id,
            result["model"],
            result["query"],
            result.get("claim"),
            result.get("severity", "clean"),
            result.get("type", "clean"),
            result["response_text"],
            result["checked_at"],
        ),
    )
    await db.commit()
    return cur.lastrowid


async def get_by_project(
    db: aiosqlite.Connection, project_id: int, limit: int = 100,
) -> list[dict]:
    """Return defamation checks for a project ordered by date desc."""
    cur = await db.execute(
        "SELECT * FROM defamation_checks WHERE project_id = ? ORDER BY checked_at DESC LIMIT ?",
        (project_id, limit),
    )
    rows = await cur.fetchall()
    return [
        {
            "id": r[0],
            "project_id": r[1],
            "model": r[2],
            "query": r[3],
            "claim": r[4],
            "severity": r[5],
            "type": r[6],
            "response_text": r[7],
            "checked_at": r[8],
        }
        for r in rows
    ]
