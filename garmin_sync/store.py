"""
store.py — SQLite storage with idempotent upsert and CSV/JSON export.

Schema is applied from schema.sql on first connect. Rows are upserted by
primary key so sync runs are safe to re-run or overlap date ranges.

Exports to data/csv/<table>.csv and data/json/<table>.json so any AI can
read the current dataset directly from a raw GitHub URL without cloning.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

_SCHEMA = Path(__file__).parent / "schema.sql"
_DATA_DIR = Path(__file__).parents[1] / "data"


def _connect(db_path: Path) -> sqlite3.Connection:
    """Open a WAL-mode SQLite connection with Row factory."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def apply_schema(conn: sqlite3.Connection) -> None:
    """Apply schema.sql (idempotent — uses CREATE TABLE IF NOT EXISTS)."""
    conn.executescript(_SCHEMA.read_text(encoding="utf-8"))
    conn.commit()


def upsert(conn: sqlite3.Connection, table: str, rows: list[dict]) -> int:
    """INSERT OR REPLACE rows into table. Returns count inserted/replaced."""
    if not rows:
        return 0
    cols = list(rows[0].keys())
    placeholders = ", ".join("?" * len(cols))
    col_list = ", ".join(cols)
    sql = f"INSERT OR REPLACE INTO {table} ({col_list}) VALUES ({placeholders})"
    values = [tuple(r.get(c) for c in cols) for r in rows]
    conn.executemany(sql, values)
    conn.commit()
    return len(rows)


def export_table(conn: sqlite3.Connection, table: str) -> None:
    """Write data/csv/<table>.csv and data/json/<table>.json."""
    df = pd.read_sql_query(f"SELECT * FROM {table} ORDER BY rowid", conn)
    csv_path = _DATA_DIR / "csv" / f"{table}.csv"
    json_path = _DATA_DIR / "json" / f"{table}.json"
    df.to_csv(csv_path, index=False, encoding="utf-8")
    # orient='records' → list of objects, matching the existing runs.json style
    df.to_json(json_path, orient="records", indent=2, force_ascii=False)


_ALL_TABLES = [
    "activities",
    "activity_laps",
    "daily_summary",
    "sleep",
    "hrv",
    "training",
    "personal_records",
    "sync_log",
]


def export_all(conn: sqlite3.Connection, tables: list[str] | None = None) -> None:
    """Export all (or specified) tables to CSV + JSON."""
    for t in (tables or _ALL_TABLES):
        export_table(conn, t)
