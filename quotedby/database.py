"""QuotedBy — Database initialization and dependency."""
from __future__ import annotations

import os

import aiosqlite
from loguru import logger

DB_PATH = os.environ.get("DB_PATH", "quotedby.db")

_SQL_INIT = """
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

CREATE TABLE IF NOT EXISTS defamation_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    model TEXT NOT NULL,
    query TEXT NOT NULL,
    claim TEXT,
    severity TEXT NOT NULL DEFAULT 'clean',
    type TEXT NOT NULL DEFAULT 'clean',
    response_text TEXT NOT NULL,
    checked_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_defamation_project ON defamation_checks(project_id);
"""


async def init_db(db: aiosqlite.Connection) -> None:
    """Create tables if not exist."""
    await db.executescript(_SQL_INIT)
    await db.commit()
    logger.info("Database initialized at {}", DB_PATH)


async def get_db(app_state) -> aiosqlite.Connection:
    """Return the shared DB connection from app state."""
    return app_state.db
