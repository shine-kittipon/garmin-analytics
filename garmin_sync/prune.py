"""
prune.py — Remove stale rows from the garmin-analytics database.

Retention policy
----------------
sync_log        90 days  — operational telemetry; short window is enough
daily_summary   730 days — 2-year health trend window
sleep           730 days
hrv             730 days

Core performance/trend tables (activities, activity_laps, training,
personal_records) are NEVER pruned — they are the long-term dataset
needed for sub-60 10K coaching.

Usage:
    python -m garmin_sync.prune          # uses the constants below
    python -m garmin_sync.prune --dry-run

The GitHub Actions prune.yml workflow runs this every Sunday 02:00 UTC.
"""
from __future__ import annotations

import argparse
import logging
from datetime import date, datetime, timedelta, timezone

from .store import _connect, ensure_db, export_all
from .sync import DB_PATH

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Retention constants (days to keep)
# ---------------------------------------------------------------------------
SYNC_LOG_RETENTION_DAYS: int = 90
HEALTH_RETENTION_DAYS: int = 730   # 2 years

# Tables pruned by ISO `date` column (YYYY-MM-DD) — never includes core tables
HEALTH_TABLES: tuple[str, ...] = ("daily_summary", "sleep", "hrv")


def prune_sync_log(conn, cutoff_utc: str, dry_run: bool = False) -> int:
    """Delete sync_log rows older than cutoff_utc (ISO-8601 UTC string).

    `ran_at_utc` is stored as an ISO string (e.g. 2026-03-30T01:00:00+00:00).
    Lexicographic comparison is correct for ISO-8601 timestamps.
    """
    if dry_run:
        row = conn.execute(
            "SELECT COUNT(*) FROM sync_log WHERE ran_at_utc < ?", (cutoff_utc,)
        ).fetchone()
        count = row[0] if row else 0
        log.info("[dry-run] sync_log: would delete %d rows older than %s", count, cutoff_utc)
        return count

    cur = conn.execute("DELETE FROM sync_log WHERE ran_at_utc < ?", (cutoff_utc,))
    conn.commit()
    log.info("sync_log: deleted %d rows older than %s", cur.rowcount, cutoff_utc)
    return cur.rowcount


def prune_health(conn, cutoff_date: str, dry_run: bool = False) -> dict[str, int]:
    """Delete rows from HEALTH_TABLES where date < cutoff_date (YYYY-MM-DD).

    All three tables use an ISO date string as their primary key, so a
    lexicographic compare against the cutoff is correct.
    """
    totals: dict[str, int] = {}
    for table in HEALTH_TABLES:
        if dry_run:
            row = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE date < ?", (cutoff_date,)
            ).fetchone()
            count = row[0] if row else 0
            log.info("[dry-run] %s: would delete %d rows older than %s", table, count, cutoff_date)
            totals[table] = count
        else:
            cur = conn.execute(f"DELETE FROM {table} WHERE date < ?", (cutoff_date,))
            conn.commit()
            log.info("%s: deleted %d rows older than %s", table, cur.rowcount, cutoff_date)
            totals[table] = cur.rowcount
    return totals


def vacuum(conn) -> None:
    """VACUUM the database to reclaim freed pages after deletes."""
    conn.execute("VACUUM")
    log.info("VACUUM complete")


def main() -> None:
    p = argparse.ArgumentParser(description="Prune stale rows from the garmin-analytics DB")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be deleted without modifying the database",
    )
    args = p.parse_args()

    log.info("=== Garmin Analytics Prune (dry_run=%s) ===", args.dry_run)

    ensure_db(DB_PATH)
    conn = _connect(DB_PATH)

    now_utc = datetime.now(timezone.utc)
    sync_log_cutoff = (now_utc - timedelta(days=SYNC_LOG_RETENTION_DAYS)).isoformat(
        timespec="seconds"
    )
    health_cutoff = (date.today() - timedelta(days=HEALTH_RETENTION_DAYS)).isoformat()

    log.info(
        "Cutoffs — sync_log: %s | health tables: %s",
        sync_log_cutoff,
        health_cutoff,
    )

    prune_sync_log(conn, sync_log_cutoff, dry_run=args.dry_run)
    prune_health(conn, health_cutoff, dry_run=args.dry_run)

    if not args.dry_run:
        vacuum(conn)
        # Re-export only the affected tables so CSV/JSON in the repo stays in sync
        export_all(conn, tables=list(HEALTH_TABLES) + ["sync_log"])
        log.info("CSV/JSON exports updated for pruned tables")

    conn.close()
    log.info("=== Prune complete ===")


if __name__ == "__main__":
    main()
