"""Database access for the course explorer.

Works against either backend, chosen at import time:

* no DATABASE_URL  -> local SQLite at data/yale_som.db (development)
* DATABASE_URL set -> Postgres, i.e. Supabase (deployment)

Callers write SQL with `?` placeholders and use the helpers below; the `?`
markers are rewritten to `%s` for Postgres. Keeping one placeholder style means
auth.py and tools.py do not care which backend is live.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

load_dotenv(ROOT / ".env")
load_dotenv(ROOT.parent / ".env")

DATABASE_URL = (os.getenv("DATABASE_URL") or "").strip()
IS_POSTGRES = DATABASE_URL.startswith(("postgres://", "postgresql://"))

SQLITE_PATH = Path(os.getenv("DB_PATH", ROOT / "data" / "yale_som.db"))


def backend() -> str:
    return "postgres" if IS_POSTGRES else "sqlite"


# --------------------------------------------------------------- connections


@contextmanager
def connect() -> Iterator[Any]:
    """Yield a connection, committing on success and rolling back on error."""
    if IS_POSTGRES:
        import psycopg
        from psycopg.rows import dict_row

        con = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    else:
        if not SQLITE_PATH.exists():
            raise FileNotFoundError(
                f"Database not found at {SQLITE_PATH}. Unzip data.zip so data/yale_som.db exists."
            )
        con = sqlite3.connect(SQLITE_PATH)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")

    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def _sql(sql: str) -> str:
    """Translate `?` placeholders to `%s` for Postgres."""
    return sql.replace("?", "%s") if IS_POSTGRES else sql


def _row_to_dict(row: Any) -> dict | None:
    if row is None:
        return None
    return dict(row)


# ------------------------------------------------------------------ helpers


def fetchall(sql: str, params: Sequence[Any] = ()) -> list[dict]:
    with connect() as con:
        cur = con.execute(_sql(sql), tuple(params))
        return [dict(r) for r in cur.fetchall()]


def fetchone(sql: str, params: Sequence[Any] = ()) -> dict | None:
    with connect() as con:
        cur = con.execute(_sql(sql), tuple(params))
        return _row_to_dict(cur.fetchone())


def execute(sql: str, params: Sequence[Any] = ()) -> int:
    """Run a statement; returns the affected row count."""
    with connect() as con:
        cur = con.execute(_sql(sql), tuple(params))
        return cur.rowcount


def insert_returning_id(sql: str, params: Sequence[Any] = ()) -> int:
    """INSERT and return the new row's id.

    SQLite exposes lastrowid; Postgres needs an explicit RETURNING clause, so
    one is appended when the caller has not written it.
    """
    with connect() as con:
        if IS_POSTGRES:
            statement = sql if "returning" in sql.lower() else f"{sql} RETURNING id"
            cur = con.execute(_sql(statement), tuple(params))
            return int(cur.fetchone()["id"])
        cur = con.execute(sql, tuple(params))
        return int(cur.lastrowid)


# -------------------------------------------------------------------- schema

SQLITE_SCHEMA = """
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

# Postgres equivalents. Case-insensitive usernames come from a unique index on
# lower(username) rather than SQLite's COLLATE NOCASE.
POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            BIGSERIAL PRIMARY KEY,
    username      TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_lower ON users (lower(username));
CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS chats (
    id         BIGSERIAL PRIMARY KEY,
    user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role       TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content    TEXT NOT NULL,
    tools_used TEXT NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_chats_user   ON chats(user_id, id);
CREATE INDEX IF NOT EXISTS idx_sessions_uid ON sessions(user_id);
"""

# Mirrors the shipped SQLite `courses` table; used when seeding Supabase.
POSTGRES_COURSES = """
CREATE TABLE IF NOT EXISTS courses (
    id BIGSERIAL PRIMARY KEY,
    course_id TEXT, course_number TEXT, course_title TEXT, course_category TEXT,
    course_type TEXT, course_session TEXT, course_description TEXT,
    faculty_1 TEXT, faculty_1_email TEXT, faculty_bio TEXT,
    daytimes TEXT, timings_day TEXT, timings_start TEXT, timings_end TEXT,
    room TEXT, section TEXT, units TEXT, term_code TEXT,
    syllabus TEXT, old_syllabus TEXT
);
"""


def init_db() -> None:
    """Create the auth/chat tables if missing. Never drops existing data."""
    with connect() as con:
        if IS_POSTGRES:
            con.execute(POSTGRES_COURSES)
            for statement in filter(str.strip, POSTGRES_SCHEMA.split(";")):
                con.execute(statement)
        else:
            con.executescript(SQLITE_SCHEMA)


def table_names() -> list[str]:
    if IS_POSTGRES:
        rows = fetchall(
            "SELECT table_name AS name FROM information_schema.tables "
            "WHERE table_schema = 'public' ORDER BY table_name"
        )
    else:
        rows = fetchall("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    return [r["name"] for r in rows]


def iter_sqlite_courses() -> Iterable[dict]:
    """Read the local catalog, for seeding Postgres."""
    con = sqlite3.connect(SQLITE_PATH)
    con.row_factory = sqlite3.Row
    try:
        for row in con.execute("SELECT * FROM courses ORDER BY id"):
            yield dict(row)
    finally:
        con.close()
