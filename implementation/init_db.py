"""Initialise the SQLite lab database.

Run directly to (re)create `lab.db` with schema and seed data:

    python implementation/init_db.py

Re-runs are idempotent: existing tables are dropped before being rebuilt so the
seed dataset stays predictable for tests and demos.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).parent / "lab.db"

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS enrollments;
DROP TABLE IF EXISTS students;
DROP TABLE IF EXISTS courses;

CREATE TABLE students (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL,
    email      TEXT    NOT NULL UNIQUE,
    cohort     TEXT    NOT NULL,
    created_at TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE courses (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    code    TEXT    NOT NULL UNIQUE,
    title   TEXT    NOT NULL,
    credits INTEGER NOT NULL CHECK (credits > 0)
);

CREATE TABLE enrollments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  INTEGER NOT NULL REFERENCES students(id),
    course_id   INTEGER NOT NULL REFERENCES courses(id),
    score       REAL    CHECK (score IS NULL OR (score >= 0 AND score <= 100)),
    enrolled_at TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (student_id, course_id)
);
"""

SEED_STUDENTS = [
    ("Alice Nguyen",   "alice@example.com",   "A1"),
    ("Bob Tran",       "bob@example.com",     "A1"),
    ("Carol Pham",     "carol@example.com",   "A2"),
    ("David Le",       "david@example.com",   "A2"),
    ("Eve Hoang",      "eve@example.com",     "B1"),
    ("Frank Vu",       "frank@example.com",   "B1"),
]

SEED_COURSES = [
    ("CS101",   "Intro to Programming", 3),
    ("CS102",   "Data Structures",      4),
    ("MATH101", "Calculus I",           4),
    ("ENG101",  "English Composition",  2),
]

# (student_id, course_id, score). IDs map to the order rows are inserted above.
SEED_ENROLLMENTS = [
    (1, 1, 92.0),
    (1, 3, 85.0),
    (2, 1, 78.5),
    (2, 2, 88.0),
    (3, 1, 65.0),
    (3, 4, 72.0),
    (4, 2, 91.0),
    (4, 3, 80.5),
    (5, 1, 55.0),
    (5, 2, 70.0),
    (6, 3, 95.0),
    (6, 4, 60.0),
]


def create_database(db_path: Path | str = DEFAULT_DB_PATH) -> Path:
    """Build a fresh database at *db_path* and return the resolved path."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.executemany(
            "INSERT INTO students (name, email, cohort) VALUES (?, ?, ?)",
            SEED_STUDENTS,
        )
        conn.executemany(
            "INSERT INTO courses (code, title, credits) VALUES (?, ?, ?)",
            SEED_COURSES,
        )
        conn.executemany(
            "INSERT INTO enrollments (student_id, course_id, score) VALUES (?, ?, ?)",
            SEED_ENROLLMENTS,
        )
        conn.commit()
    finally:
        conn.close()
    return db_path


def _smoke_summary(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        for table in ("students", "courses", "enrollments"):
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  {table:<12} {count} rows")
    finally:
        conn.close()


if __name__ == "__main__":
    path = create_database()
    print(f"Database created at: {path}")
    _smoke_summary(path)
