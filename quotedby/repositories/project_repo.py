"""QuotedBy — Project repository (DB operations)."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import aiosqlite


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row: tuple) -> dict:
    return {
        "id": row[0],
        "name": row[1],
        "category": row[2],
        "competitors": json.loads(row[3]),
        "queries": json.loads(row[4]),
        "url": row[5],
        "created_at": row[6],
    }


async def create(db: aiosqlite.Connection, data: dict) -> dict:
    """Insert a new project and return it."""
    now = _now()
    competitors = data.get("competitors", [])
    queries = data.get("queries", [])
    cur = await db.execute(
        "INSERT INTO projects (name, category, competitors, queries, url, created_at) VALUES (?,?,?,?,?,?)",
        (
            data["name"],
            data["category"],
            json.dumps(competitors),
            json.dumps(queries),
            data.get("url"),
            now,
        ),
    )
    await db.commit()
    return {
        **data,
        "id": cur.lastrowid,
        "created_at": now,
        "competitors": competitors,
        "queries": queries,
    }


async def list_all(db: aiosqlite.Connection) -> list[dict]:
    """Return all projects ordered by creation date desc."""
    cur = await db.execute("SELECT * FROM projects ORDER BY created_at DESC")
    rows = await cur.fetchall()
    return [_row_to_dict(r) for r in rows]


async def get_by_id(db: aiosqlite.Connection, project_id: int) -> dict | None:
    """Return a project by ID or None."""
    cur = await db.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    row = await cur.fetchone()
    if not row:
        return None
    return _row_to_dict(row)


async def update(db: aiosqlite.Connection, project_id: int, data: dict) -> dict | None:
    """Update a project and return updated version."""
    proj = await get_by_id(db, project_id)
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
    return await get_by_id(db, project_id)


async def delete(db: aiosqlite.Connection, project_id: int) -> bool:
    """Delete a project and all its related data."""
    cur = await db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    await db.execute("DELETE FROM scans WHERE project_id = ?", (project_id,))
    await db.execute("DELETE FROM defamation_checks WHERE project_id = ?", (project_id,))
    await db.commit()
    return cur.rowcount > 0
