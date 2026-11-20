# Case log stored in SQLite (cases.db). Each warning is a case that stays
# open until it's closed as a real issue or a false alarm.

import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

DATABASE_FILE = Path(__file__).parent / "cases.db"


def connect():
    return sqlite3.connect(DATABASE_FILE)


def create_table():
    with connect() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS cases (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                opened_at    TEXT NOT NULL,
                recording    TEXT NOT NULL,
                finding      TEXT NOT NULL,
                score        REAL NOT NULL,
                status       TEXT NOT NULL DEFAULT 'open',
                outcome      TEXT,
                action_taken TEXT,
                closed_at    TEXT
            )
            """
        )


def has_case(recording):
    # Prevents logging the same recording twice when scanning again
    with connect() as db:
        row = db.execute(
            "SELECT COUNT(*) FROM cases WHERE recording = ?",
            (recording,),
        ).fetchone()
    return row[0] > 0


def get_case(recording):
    with connect() as db:
        db.row_factory = sqlite3.Row
        row = db.execute(
            "SELECT * FROM cases WHERE recording = ? ORDER BY id DESC LIMIT 1",
            (recording,),
        ).fetchone()
    return dict(row) if row else None


def open_case(recording, finding, score):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    with connect() as db:
        db.execute(
            "INSERT INTO cases (opened_at, recording, finding, score) VALUES (?, ?, ?, ?)",
            (now, recording, finding, score),
        )


def close_case(case_id, outcome, action_taken):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    with connect() as db:
        db.execute(
            """
            UPDATE cases
            SET status = 'closed', outcome = ?, action_taken = ?, closed_at = ?
            WHERE id = ?
            """,
            (outcome, action_taken, now, case_id),
        )


def list_cases():
    with connect() as db:
        return pd.read_sql_query(
            """
            SELECT id, status, recording, finding, ROUND(score) AS score,
                   opened_at, outcome, action_taken, closed_at
            FROM cases
            ORDER BY status DESC, score DESC  -- open cases first, strongest fault on top
            """,
            db,
        )


def summary():
    with connect() as db:
        row = db.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN status = 'closed' THEN 1 ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN outcome = 'real issue' THEN 1 ELSE 0 END), 0)
            FROM cases
            """
        ).fetchone()
    return {"open": row[0], "closed": row[1], "real_issues": row[2]}


def delete_all_cases():
    with connect() as db:
        db.execute("DELETE FROM cases")
