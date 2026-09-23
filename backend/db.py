"""SQLite access and schema setup for the course explorer.

The `courses` table ships pre-populated in data/yale_som.db. This module adds
the `users`, `sessions` and `chats` tables around it without touching it.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

# DB_PATH is overridable so a deployment can point somewhere else.
DB_PATH = Path(os.getenv("DB_PATH", ROOT / "data" / "yale_som.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chats (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role       TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content    TEXT NOT NULL,
    tools_used TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_chats_user   ON chats(user_id, id);
CREATE INDEX IF NOT EXISTS idx_sessions_uid ON sessions(user_id);
"""


def connect() -> sqlite3.Connection:
    """Open a connection with rows as mappings and FKs enforced."""
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init_db() -> None:
    """Create the auth/chat tables if they are missing. Never drops anything."""
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DB_PATH}. Unzip data.zip so data/yale_som.db exists."
        )
    with connect() as con:
        con.executescript(SCHEMA)


def table_names() -> list[str]:
    with connect() as con:
        rows = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    return [r["name"] for r in rows]
