"""
db.py — SQLite database layer for ACEest Fitness & Gym.

Responsibilities:
    - Create tables on first run
    - Provide CRUD functions for clients, progress, and workouts
    - Return plain dicts (not sqlite3.Row objects) so they are JSON-serializable

Design choices:
    - Single file DB (aceest_fitness.db) — simple, portable, no server needed
    - DB path configurable via DB_PATH constant — makes testing easy
      (tests can monkeypatch it to a temp file)
    - Row factory set to sqlite3.Row → supports dict-like access
"""

import sqlite3
from pathlib import Path

# Default DB file — sits next to this module.
# Tests will monkeypatch this to a temp location.
DB_PATH = str(Path(__file__).parent / "aceest_fitness.db")


# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

def _connect() -> sqlite3.Connection:
    """Open a connection with Row factory and foreign keys ON."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # allows dict(row) conversion
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ---------------------------------------------------------------------------
# Schema initialization
# ---------------------------------------------------------------------------

def init_db() -> None:
    """
    Create tables if they don't exist.
    Safe to call on every app startup — idempotent.
    """
    conn = _connect()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS clients (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                name              TEXT UNIQUE NOT NULL,
                age               INTEGER,
                height            REAL,
                weight            REAL,
                program           TEXT,
                calories          INTEGER,
                target_weight     REAL,
                target_adherence  INTEGER
            );

            CREATE TABLE IF NOT EXISTS progress (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                client_name  TEXT NOT NULL,
                week         TEXT NOT NULL,
                adherence    INTEGER CHECK (adherence BETWEEN 0 AND 100)
            );

            CREATE TABLE IF NOT EXISTS workouts (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                client_name   TEXT NOT NULL,
                date          TEXT NOT NULL,
                workout_type  TEXT,
                duration_min  INTEGER,
                notes         TEXT
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Clients — CRUD
# ---------------------------------------------------------------------------

def upsert_client(data: dict) -> dict:
    """
    Insert or replace a client by name.
    Returns the stored client as a dict.
    """
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO clients
                (name, age, height, weight, program,
                 calories, target_weight, target_adherence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                age              = excluded.age,
                height           = excluded.height,
                weight           = excluded.weight,
                program          = excluded.program,
                calories         = excluded.calories,
                target_weight    = excluded.target_weight,
                target_adherence = excluded.target_adherence
            """,
            (
                data["name"],
                data.get("age"),
                data.get("height"),
                data.get("weight"),
                data.get("program"),
                data.get("calories"),
                data.get("target_weight"),
                data.get("target_adherence"),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return get_client(data["name"])


def get_client(name: str) -> dict | None:
    """Return the client dict, or None if not found."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM clients WHERE name = ?", (name,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_clients() -> list[dict]:
    """Return all clients ordered by name."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM clients ORDER BY name"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def delete_client(name: str) -> bool:
    """Delete a client. Returns True if a row was deleted."""
    conn = _connect()
    try:
        cur = conn.execute("DELETE FROM clients WHERE name = ?", (name,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Progress — weekly adherence entries
# ---------------------------------------------------------------------------

def log_progress(client_name: str, week: str, adherence: int) -> dict:
    """Insert a weekly progress entry. Returns the inserted row."""
    if not 0 <= adherence <= 100:
        raise ValueError("Adherence must be between 0 and 100")
    conn = _connect()
    try:
        cur = conn.execute(
            """
            INSERT INTO progress (client_name, week, adherence)
            VALUES (?, ?, ?)
            """,
            (client_name, week, adherence),
        )
        conn.commit()
        new_id = cur.lastrowid
        row = conn.execute(
            "SELECT * FROM progress WHERE id = ?", (new_id,)
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def get_progress(client_name: str) -> list[dict]:
    """Return all progress entries for a client, ordered by insertion."""
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT week, adherence FROM progress
            WHERE client_name = ?
            ORDER BY id
            """,
            (client_name,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Workouts — logging
# ---------------------------------------------------------------------------

def log_workout(
    client_name: str,
    date: str,
    workout_type: str,
    duration_min: int,
    notes: str = "",
) -> dict:
    """Insert a workout entry. Returns the inserted row."""
    conn = _connect()
    try:
        cur = conn.execute(
            """
            INSERT INTO workouts
                (client_name, date, workout_type, duration_min, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (client_name, date, workout_type, duration_min, notes),
        )
        conn.commit()
        new_id = cur.lastrowid
        row = conn.execute(
            "SELECT * FROM workouts WHERE id = ?", (new_id,)
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def get_workouts(client_name: str) -> list[dict]:
    """Return all workouts for a client, newest first."""
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT date, workout_type, duration_min, notes
            FROM workouts
            WHERE client_name = ?
            ORDER BY date DESC, id DESC
            """,
            (client_name,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()