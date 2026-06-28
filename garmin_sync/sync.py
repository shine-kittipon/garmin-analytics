"""
sync.py — Orchestrator for the daily Garmin data pull.

Usage:
    python -m garmin_sync.sync --days 30
    python -m garmin_sync.sync --start 2026-01-01 --end 2026-06-28
    python -m garmin_sync.sync --days 365   # backfill a full year

The script is designed to be idempotent: re-running the same date range
upserts rows by primary key, so no duplicates accumulate.
"""
from __future__ import annotations

import argparse
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .auth import get_client
from .source import GarminConnectSource
from .endpoints import (
    fetch_activities,
    fetch_activity_hr_zones,
    fetch_activity_laps,
    fetch_body_battery,
    fetch_daily_summaries,
    fetch_hrv,
    fetch_personal_records,
    fetch_rhr,
    fetch_sleep,
    fetch_stress,
    fetch_training,
)
from .transform import (
    to_activity,
    to_daily_summary,
    to_hrv,
    to_laps,
    to_personal_record,
    to_sleep,
    to_training,
)
from .store import _connect, apply_schema, ensure_db, export_all, upsert

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger(__name__)

DB_PATH = Path(__file__).parents[1] / "data" / "db" / "garmin.sqlite"


def resolve_range(
    days: int,
    start_arg: str | None,
    end_arg: str | None,
) -> tuple[str, str]:
    if start_arg and end_arg:
        return start_arg, end_arg
    end = date.today().isoformat()
    start = (date.today() - timedelta(days=days)).isoformat()
    return start, end


def run_sync(
    days: int = 30,
    start_arg: str | None = None,
    end_arg: str | None = None,
) -> dict:
    start, end = resolve_range(days, start_arg, end_arg)
    log.info("=== Garmin Analytics Sync: %s → %s ===", start, end)

    ensure_db(DB_PATH)          # rebuild from CSV if no local .sqlite exists

    client = get_client()
    source = GarminConnectSource(client)

    conn = _connect(DB_PATH)
    apply_schema(conn)

    # ------------------------------------------------------------------ #
    # 1. Activities + laps + HR zones
    # ------------------------------------------------------------------ #
    raw_activities = fetch_activities(source, start, end)
    activity_rows: list[dict] = []
    lap_rows: list[dict] = []

    for a in raw_activities:
        aid = a.get("activityId")
        zones = fetch_activity_hr_zones(source, aid) if aid else []
        activity_rows.append(to_activity(a, zones))
        laps = fetch_activity_laps(source, aid) if aid else []
        lap_rows.extend(to_laps(aid, laps))

    n_activities = upsert(conn, "activities", activity_rows)
    n_laps = upsert(conn, "activity_laps", lap_rows)
    log.info("Activities: %d rows, Laps: %d rows", n_activities, n_laps)

    # ------------------------------------------------------------------ #
    # 2. Daily health
    # ------------------------------------------------------------------ #
    raw_daily = fetch_daily_summaries(source, start, end)
    raw_rhr = fetch_rhr(source, start, end)
    raw_stress = fetch_stress(source, start, end)
    raw_bb = fetch_body_battery(source, start, end)

    # Build date-keyed lookup dicts for merging into daily_summary rows
    rhr_by_date: dict[str, int] = {}
    for r in raw_rhr:
        d = (r.get("calendarDate") or r.get("date") or "")[:10]
        v = r.get("value") or r.get("restingHeartRate")
        if d and v is not None:
            rhr_by_date[d] = int(v)

    stress_by_date: dict[str, int] = {}
    for r in raw_stress:
        d = r.get("_date") or (r.get("calendarDate") or "")[:10]
        v = r.get("overallStressLevel") or r.get("avgStressLevel")
        if d and v is not None:
            stress_by_date[d] = int(v)

    bb_by_date: dict[str, dict] = {}
    for r in raw_bb:
        # Body battery may be returned as [date, min, max] list or as dicts
        if isinstance(r, list) and len(r) >= 3:
            bb_by_date[str(r[0])[:10]] = {"min": r[1], "max": r[2]}
        elif isinstance(r, dict):
            d = (r.get("calendarDate") or r.get("startTimestampLocal") or "")[:10]
            if d:
                bb_by_date[d] = {
                    "min": r.get("bodyBatteryDuringSleep"),
                    "max": r.get("bodyBatteryAtWakeTime"),
                }

    daily_rows = [
        to_daily_summary(r, rhr_by_date, stress_by_date, bb_by_date)
        for r in raw_daily
    ]
    n_daily = upsert(conn, "daily_summary", daily_rows)
    log.info("Daily summaries: %d rows", n_daily)

    # ------------------------------------------------------------------ #
    # 3. Sleep
    # ------------------------------------------------------------------ #
    raw_sleep = fetch_sleep(source, start, end)
    sleep_rows = [r for r in (to_sleep(s) for s in raw_sleep) if r]
    n_sleep = upsert(conn, "sleep", sleep_rows)
    log.info("Sleep: %d rows", n_sleep)

    # ------------------------------------------------------------------ #
    # 4. HRV
    # ------------------------------------------------------------------ #
    raw_hrv = fetch_hrv(source, start, end)
    hrv_rows = [r for r in (to_hrv(h) for h in raw_hrv) if r]
    n_hrv = upsert(conn, "hrv", hrv_rows)
    log.info("HRV: %d rows", n_hrv)

    # ------------------------------------------------------------------ #
    # 5. Training status / readiness / VO2max
    # ------------------------------------------------------------------ #
    raw_training = fetch_training(source, start, end)
    training_rows = [r for r in (to_training(t) for t in raw_training) if r]
    n_training = upsert(conn, "training", training_rows)
    log.info("Training: %d rows", n_training)

    # ------------------------------------------------------------------ #
    # 6. Personal records (full refresh each sync)
    # ------------------------------------------------------------------ #
    raw_records = fetch_personal_records(source)
    record_rows = [to_personal_record(r) for r in raw_records]
    n_records = upsert(conn, "personal_records", record_rows)
    log.info("Personal records: %d rows", n_records)

    # ------------------------------------------------------------------ #
    # 7. Sync log
    # ------------------------------------------------------------------ #
    log_row = {
        "ran_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "range_start": start,
        "range_end": end,
        "rows_activities": n_activities,
        "rows_laps": n_laps,
        "rows_daily": n_daily,
        "rows_sleep": n_sleep,
        "rows_hrv": n_hrv,
        "rows_training": n_training,
        "source": "garminconnect",
    }
    upsert(conn, "sync_log", [log_row])

    # ------------------------------------------------------------------ #
    # 8. Export CSV + JSON for direct AI / browser access
    # ------------------------------------------------------------------ #
    export_all(conn)
    conn.close()

    log.info("=== Sync complete ===")
    return log_row


def main() -> None:
    p = argparse.ArgumentParser(description="Sync Garmin data to the analytics database")
    p.add_argument("--days", type=int, default=30, help="Days to look back (default: 30)")
    p.add_argument("--start", help="Start date YYYY-MM-DD (use together with --end)")
    p.add_argument("--end", help="End date YYYY-MM-DD")
    args = p.parse_args()
    run_sync(args.days, args.start, args.end)


if __name__ == "__main__":
    main()
