"""Account creation, login and session tokens.

Passwords are stored as bcrypt hashes. bcrypt generates a random salt per
password and embeds it in the hash string, so there is no separate salt
column — `checkpw` reads the salt back out of the stored hash.
"""

from __future__ import annotations

import json
import secrets
import sqlite3

import bcrypt

from db import connect

MIN_USERNAME = 3
MIN_PASSWORD = 8

# bcrypt truncates silently past 72 bytes; reject instead of quietly ignoring.
MAX_PASSWORD_BYTES = 72


class AuthError(Exception):
    """Raised for any bad credential or validation problem."""


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _validate(username: str, password: str) -> tuple[str, str]:
    username = (username or "").strip()
    password = password or ""
    if len(username) < MIN_USERNAME:
        raise AuthError(f"Username must be at least {MIN_USERNAME} characters.")
    if len(password) < MIN_PASSWORD:
        raise AuthError(f"Password must be at least {MIN_PASSWORD} characters.")
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise AuthError("Password is too long (max 72 bytes).")
    return username, password


def create_user(username: str, password: str) -> dict:
    """Create an account and return a fresh session."""
    username, password = _validate(username, password)
    with connect() as con:
        try:
            cur = con.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, hash_password(password)),
            )
        except sqlite3.IntegrityError as exc:
            raise AuthError("That username is already taken.") from exc
        user_id = int(cur.lastrowid)
    return {"token": _new_session(user_id), "username": username, "user_id": user_id}


def login(username: str, password: str) -> dict:
    """Check credentials and return a fresh session."""
    username = (username or "").strip()
    with connect() as con:
        row = con.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()

    # Same message either way, so the response cannot be used to discover
    # which usernames exist.
    if row is None or not verify_password(password, row["password_hash"]):
        raise AuthError("Incorrect username or password.")

    return {
        "token": _new_session(int(row["id"])),
        "username": row["username"],
        "user_id": int(row["id"]),
    }


def _new_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    with connect() as con:
        con.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user_id))
    return token


def user_for_token(token: str | None) -> dict | None:
    """Resolve a session token to its user, or None if unknown."""
    if not token:
        return None
    with connect() as con:
        row = con.execute(
            """
            SELECT users.id AS id, users.username AS username
            FROM sessions JOIN users ON users.id = sessions.user_id
            WHERE sessions.token = ?
            """,
            (token,),
        ).fetchone()
    return {"user_id": int(row["id"]), "username": row["username"]} if row else None


def logout(token: str | None) -> None:
    if not token:
        return
    with connect() as con:
        con.execute("DELETE FROM sessions WHERE token = ?", (token,))


# ---------------------------------------------------------------- chat history


def save_message(user_id: int, role: str, content: str, tools_used: list[str] | None = None) -> None:
    with connect() as con:
        con.execute(
            "INSERT INTO chats (user_id, role, content, tools_used) VALUES (?, ?, ?, ?)",
            (user_id, role, content, json.dumps(tools_used or [])),
        )


def history(user_id: int, limit: int = 200) -> list[dict]:
    """Return this user's messages oldest-first."""
    with connect() as con:
        rows = con.execute(
            """
            SELECT role, content, tools_used, created_at
            FROM chats WHERE user_id = ? ORDER BY id DESC LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    out = []
    for row in reversed(rows):
        try:
            tools = json.loads(row["tools_used"])
        except (ValueError, TypeError):
            tools = []
        out.append(
            {
                "role": row["role"],
                "content": row["content"],
                "tools_used": tools,
                "created_at": row["created_at"],
            }
        )
    return out


def clear_history(user_id: int) -> int:
    with connect() as con:
        cur = con.execute("DELETE FROM chats WHERE user_id = ?", (user_id,))
    return cur.rowcount
