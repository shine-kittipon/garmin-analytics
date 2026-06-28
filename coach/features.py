"""
features.py — Compute analytical features from the database for the AI coach.

Provides structured summaries that the coach can reason over:
- Rolling load (acute 7-day vs chronic 28-day, normalised to weekly ratio)
- Pace and VO2max trend
- Sleep and HRV recovery
- Sub-60 10K projection (Riegel formula from recent qualifying runs)
"""
from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from garmin_sync.store import ensure_db

DB_PATH = Path(__file__).parents[1] / "data" / "db" / "garmin.sqlite"

# Sub-60 10K goal constants (carried over from garmin-runs project)
GOAL_PACE = 6.0     # min/km → 60 min / 10 km
MIN_KM = 3.0        # minimum distance to count as a qualifying run
GOAL_DISTANCE = 10.0


@dataclass
class CoachSummary:
    as_of: str
    recent_runs: list[dict]
    weekly_km: float | None
    acute_load_7d: float | None
    chronic_load_28d: float | None
    load_ratio: float | None              # acute / (chronic/4); flag if > 1.5 or < 0.8
    pace_trend_min_km: list[dict]         # [{date, pace_min_km}] oldest-first, last 8 runs
    vo2max_latest: float | None
    vo2max_trend: list[dict]              # [{date, vo2max}] oldest-first
    avg_sleep_score_7d: float | None
    avg_hrv_7d: float | None
    resting_hr_7d: float | None
    recovery_status: str | None           # 'good' | 'moderate' | 'poor'
    sub60_projection: dict                # {predicted_pace, predicted_time_min, gap_min, ready, ...}
    training_status: str | None
    training_readiness: int | None


def _conn() -> sqlite3.Connection:
    ensure_db(DB_PATH)  # rebuild from CSV if no local .sqlite exists
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _q(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def riegel_predict(dist_km: float, time_min: float, target_km: float) -> float:
    """Riegel formula: T2 = T1 × (D2/D1)^1.06. Returns predicted time in minutes."""
    return time_min * (target_km / dist_km) ** 1.06


def sub60_projection(conn: sqlite3.Connection) -> dict:
    """Estimate 10K finish time from the most recent qualifying run via Riegel formula."""
    runs = _q(conn, """
        SELECT date, distance_km, duration_min, pace_min_km
        FROM activities
        WHERE distance_km >= ? AND pace_min_km IS NOT NULL
        ORDER BY date DESC LIMIT 5
    """, (MIN_KM,))

    if not runs:
        return {
            "predicted_pace": None,
            "predicted_time_min": None,
            "gap_min": None,
            "ready": False,
            "note": "No qualifying runs found (need distance >= 3 km)",
        }

    # Use most recent run as the performance sample
    best = runs[0]
    predicted_time = riegel_predict(
        best["distance_km"], best["duration_min"], GOAL_DISTANCE
    )
    predicted_pace = predicted_time / GOAL_DISTANCE
    goal_time = GOAL_DISTANCE * GOAL_PACE  # 60 min

    return {
        "predicted_pace": round(predicted_pace, 3),
        "predicted_time_min": round(predicted_time, 1),
        "gap_min": round(predicted_time - goal_time, 1),
        "ready": predicted_time <= goal_time,
        "based_on_run_date": best["date"],
        "based_on_run_distance_km": best["distance_km"],
    }


def build_summary(as_of: str | None = None) -> CoachSummary:
    """Build a full CoachSummary from the database as of the given date."""
    as_of = as_of or date.today().isoformat()
    d7 = (date.fromisoformat(as_of) - timedelta(days=7)).isoformat()
    d28 = (date.fromisoformat(as_of) - timedelta(days=28)).isoformat()

    conn = _conn()

    recent_runs = _q(conn, """
        SELECT date, distance_km, duration_min, pace_min_km, avg_hr, vo2max, aerobic_te
        FROM activities
        WHERE date >= ? AND distance_km >= ?
        ORDER BY date DESC LIMIT 10
    """, (d28, MIN_KM))

    # Weekly volume
    weekly_km_row = _q(conn, """
        SELECT COALESCE(SUM(distance_km), 0) AS km
        FROM activities WHERE date >= ? AND distance_km >= ?
    """, (d7, MIN_KM))
    weekly_km = weekly_km_row[0]["km"] if weekly_km_row else None

    # Training load: aerobic training effect summed as load proxy
    acute_row = _q(conn, """
        SELECT COALESCE(SUM(aerobic_te), 0) AS load
        FROM activities WHERE date >= ? AND distance_km >= ?
    """, (d7, MIN_KM))
    chronic_row = _q(conn, """
        SELECT COALESCE(SUM(aerobic_te), 0) AS load
        FROM activities WHERE date >= ? AND distance_km >= ?
    """, (d28, MIN_KM))

    acute_load = acute_row[0]["load"] if acute_row else None
    chronic_load_28 = chronic_row[0]["load"] if chronic_row else None
    # Normalise 28-day chronic to weekly equivalent before computing ratio
    chronic_weekly = (chronic_load_28 / 4) if chronic_load_28 else None
    load_ratio = (
        round(acute_load / chronic_weekly, 2)
        if acute_load and chronic_weekly and chronic_weekly > 0
        else None
    )

    # Pace trend — most recent 8 qualifying runs, returned oldest-first
    pace_trend = _q(conn, """
        SELECT date, pace_min_km FROM activities
        WHERE distance_km >= ? AND pace_min_km IS NOT NULL
        ORDER BY date DESC LIMIT 8
    """, (MIN_KM,))

    # VO2max trend
    vo2max_latest_row = _q(conn, """
        SELECT vo2max FROM activities WHERE vo2max IS NOT NULL ORDER BY date DESC LIMIT 1
    """)
    vo2max_latest = vo2max_latest_row[0]["vo2max"] if vo2max_latest_row else None

    vo2max_trend = _q(conn, """
        SELECT date, vo2max FROM activities WHERE vo2max IS NOT NULL ORDER BY date DESC LIMIT 8
    """)

    # Sleep quality
    sleep_row = _q(conn, "SELECT AVG(sleep_score) AS avg FROM sleep WHERE date >= ?", (d7,))
    avg_sleep = sleep_row[0]["avg"] if sleep_row else None

    # HRV
    hrv_row = _q(conn, "SELECT AVG(last_night_avg) AS avg FROM hrv WHERE date >= ?", (d7,))
    avg_hrv = hrv_row[0]["avg"] if hrv_row else None

    # Resting HR
    rhr_row = _q(conn, """
        SELECT AVG(resting_hr) AS avg FROM daily_summary
        WHERE date >= ? AND resting_hr IS NOT NULL
    """, (d7,))
    rhr = rhr_row[0]["avg"] if rhr_row else None

    # Training status from most recent training record
    training_row = _q(conn, """
        SELECT training_status, training_readiness_score
        FROM training ORDER BY date DESC LIMIT 1
    """)
    t_status = training_row[0]["training_status"] if training_row else None
    t_readiness = training_row[0]["training_readiness_score"] if training_row else None

    # Simple recovery classification from HRV
    recovery: str | None = None
    if avg_hrv is not None:
        recovery = "good" if avg_hrv > 50 else "moderate" if avg_hrv > 35 else "poor"

    projection = sub60_projection(conn)
    conn.close()

    return CoachSummary(
        as_of=as_of,
        recent_runs=recent_runs,
        weekly_km=round(weekly_km, 1) if weekly_km is not None else None,
        acute_load_7d=round(acute_load, 1) if acute_load else None,
        chronic_load_28d=round(chronic_load_28, 1) if chronic_load_28 else None,
        load_ratio=load_ratio,
        pace_trend_min_km=list(reversed(pace_trend)),
        vo2max_latest=vo2max_latest,
        vo2max_trend=list(reversed(vo2max_trend)),
        avg_sleep_score_7d=round(avg_sleep, 1) if avg_sleep is not None else None,
        avg_hrv_7d=round(avg_hrv, 1) if avg_hrv is not None else None,
        resting_hr_7d=round(rhr, 1) if rhr is not None else None,
        recovery_status=recovery,
        sub60_projection=projection,
        training_status=t_status,
        training_readiness=t_readiness,
    )


def summary_as_dict(as_of: str | None = None) -> dict[str, Any]:
    return asdict(build_summary(as_of))
