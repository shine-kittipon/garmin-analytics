"""
store.py — SQLite storage with idempotent upsert and CSV/JSON export.

Schema is applied from schema.sql on first connect. Rows are upserted by
primary key so sync runs are safe to re-run or overlap date ranges.

Exports to data/csv/<table>.csv and data/json/<table>.json so any AI can
read the current dataset directly from a raw GitHub URL without cloning.

garmin.sqlite is NOT tracked in git; the committed CSV/JSON files are the
source of truth. rebuild_db_from_csv() / ensure_db() rebuild the binary
from CSV on a fresh checkout so sync and MCP consumers work without a
pre-existing .sqlite file.
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

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
    # Drop rows where every non-key field is null (Garmin placeholder entries)
    key_cols = {"date", "activity_id", "record_id", "lap_index"}
    value_cols = [c for c in df.columns if c not in key_cols]
    if value_cols:
        df = df[df[value_cols].notna().any(axis=1)]
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


def rebuild_db_from_csv(db_path: Path) -> None:
    """Rebuild garmin.sqlite from the committed CSV exports.

    Reads data/csv/<table>.csv for every table in _ALL_TABLES and upserts
    the rows into a freshly schema-initialised database. Safe to call on an
    existing DB — rows are upserted by primary key (idempotent).
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = _connect(db_path)
    apply_schema(conn)
    csv_dir = _DATA_DIR / "csv"
    for table in _ALL_TABLES:
        csv_path = csv_dir / f"{table}.csv"
        if not csv_path.exists():
            log.debug("rebuild_db_from_csv: %s not found, skipping", csv_path)
            continue
        df = pd.read_csv(csv_path, dtype=str)          # read as str; upsert handles typing
        if df.empty:
            continue
        rows = df.where(pd.notna(df), None).to_dict(orient="records")
        n = upsert(conn, table, rows)
        log.info("rebuild_db_from_csv: %s — %d rows loaded", table, n)
    conn.close()


def ensure_db(db_path: Path) -> None:
    """Ensure the SQLite database exists; rebuild from CSV if it is missing."""
    if not db_path.exists():
        log.info("garmin.sqlite not found — rebuilding from CSV exports")
        rebuild_db_from_csv(db_path)
