"""Copy the local SQLite catalog into Supabase Postgres.

Usage (from backend/, with DATABASE_URL set in .env):

    .venv/bin/python migrate_to_supabase.py            # create tables + seed courses
    .venv/bin/python migrate_to_supabase.py --check    # report only, change nothing

Safe to re-run: tables are created IF NOT EXISTS, and courses are only seeded
when the target table is empty (use --force to reseed).
"""

from __future__ import annotations

import sys

import db

COLUMNS = [
    "course_id", "course_number", "course_title", "course_category",
    "course_type", "course_session", "course_description",
    "faculty_1", "faculty_1_email", "faculty_bio",
    "daytimes", "timings_day", "timings_start", "timings_end",
    "room", "section", "units", "term_code", "syllabus", "old_syllabus",
]


def main() -> int:
    check_only = "--check" in sys.argv
    force = "--force" in sys.argv

    if not db.IS_POSTGRES:
        print("DATABASE_URL is not set to a Postgres URL.")
        print("Add your Supabase connection string to .env as DATABASE_URL, then re-run.")
        return 1

    print("target: Postgres (Supabase)")

    if check_only:
        print("tables:", db.table_names())
        row = db.fetchone("SELECT COUNT(*) AS n FROM courses")
        print("courses rows:", row["n"] if row else "table missing")
        return 0

    print("creating tables if missing...")
    db.init_db()
    print("tables:", db.table_names())

    existing = db.fetchone("SELECT COUNT(*) AS n FROM courses")
    count = int(existing["n"]) if existing else 0
    if count and not force:
        print(f"courses already has {count} rows; skipping seed (use --force to reseed)")
        return 0

    if force and count:
        print(f"--force: clearing {count} existing course rows")
        db.execute("DELETE FROM courses")

    rows = list(db.iter_sqlite_courses())
    print(f"copying {len(rows)} courses from local SQLite...")

    placeholders = ", ".join(["?"] * len(COLUMNS))
    sql = f"INSERT INTO courses ({', '.join(COLUMNS)}) VALUES ({placeholders})"
    for row in rows:
        db.execute(sql, [row.get(c) for c in COLUMNS])

    final = db.fetchone("SELECT COUNT(*) AS n FROM courses")
    print("done. courses in Supabase:", final["n"] if final else "?")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
