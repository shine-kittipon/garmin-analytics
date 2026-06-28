"""
transform.py — Convert raw Garmin API responses to normalized schema rows.

All numeric coercions go through _r() so missing/null metrics become None.
Speeds are converted from m/s → km/h. Dates are ISO YYYY-MM-DD strings.
The hr_zone_pcts() helper is ported from the existing garmin_pull.py.
"""
from __future__ import annotations

from typing import Any


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _r(v: Any, n: int = 1) -> float | int | None:
    """Round v to n decimal places if numeric, else None."""
    return round(v, n) if isinstance(v, (int, float)) else None


def _int(v: Any) -> int | None:
    return int(v) if isinstance(v, (int, float)) else None


def _str(v: Any) -> str | None:
    return str(v) if v is not None else None


def _pace(dist_km: float | None, dur_min: float | None) -> float | None:
    if dist_km and dur_min and dist_km > 0:
        return round(dur_min / dist_km, 3)
    return None


# --------------------------------------------------------------------------- #
# HR zone percentage helper (ported from garmin_pull.py)
# --------------------------------------------------------------------------- #

def hr_zone_pcts(zones: list[dict]) -> dict[str, float | None]:
    """Convert get_activity_hr_in_timezones response to hr_z1_pct … hr_z5_pct fields."""
    total = sum((z.get("secsInZone") or 0) for z in zones)
    out: dict[str, float | None] = {f"hr_z{n}_pct": None for n in range(1, 6)}
    if total <= 0:
        return out
    for z in zones:
        n = z.get("zoneNumber")
        if n in (1, 2, 3, 4, 5):
            out[f"hr_z{n}_pct"] = round((z.get("secsInZone") or 0) / total * 100, 1)
    return out


# --------------------------------------------------------------------------- #
# Activities
# --------------------------------------------------------------------------- #

def to_activity(raw: dict, zone_rows: list[dict]) -> dict:
    """Raw activity summary + zone rows → normalized activities row."""
    dist_km = (raw.get("distance") or 0) / 1000
    dur_min = (raw.get("duration") or 0) / 60

    # activityType may be a dict or a plain string depending on API version
    act_type = raw.get("activityType")
    activity_type = (
        act_type.get("typeKey") if isinstance(act_type, dict) else _str(act_type)
    )

    return {
        "activity_id": raw.get("activityId"),
        "date": (raw.get("startTimeLocal") or "")[:10],
        "activity_type": activity_type,
        "activity_name": raw.get("activityName"),
        "distance_km": round(dist_km, 2),
        "duration_min": round(dur_min, 2),
        "pace_min_km": _pace(dist_km, dur_min),
        "avg_hr": _int(raw.get("averageHR")),
        "max_hr": _int(raw.get("maxHR")),
        **hr_zone_pcts(zone_rows),
        "avg_cadence": _r(raw.get("averageRunningCadenceInStepsPerMinute"), 0),
        "max_cadence": _r(raw.get("maxRunningCadenceInStepsPerMinute"), 0),
        "vo2max": _r(raw.get("vO2MaxValue"), 1),
        "aerobic_te": _r(raw.get("aerobicTrainingEffect"), 1),
        "anaerobic_te": _r(raw.get("anaerobicTrainingEffect"), 1),
        "avg_power": _r(raw.get("avgPower"), 0),
        "max_power": _r(raw.get("maxPower"), 0),
        # Garmin returns speeds in m/s — convert to km/h
        "avg_speed_kmh": _r((raw.get("averageSpeed") or 0) * 3.6, 2) if raw.get("averageSpeed") else None,
        "max_speed_kmh": _r((raw.get("maxSpeed") or 0) * 3.6, 2) if raw.get("maxSpeed") else None,
        "stride_length_cm": _r(raw.get("avgStrideLength"), 1),
        "ground_contact_ms": _r(raw.get("avgGroundContactTime"), 0),
        "vertical_oscillation_cm": _r(raw.get("avgVerticalOscillation"), 1),
        "elevation_gain_m": round(raw.get("elevationGain", 0) or 0, 1),
        "calories": _int(raw.get("calories")),
        "training_load": _r(raw.get("activityTrainingLoad"), 1),
    }


def to_laps(activity_id: int, raw_laps: list[dict]) -> list[dict]:
    """Raw lap dicts → normalized activity_laps rows."""
    rows = []
    for i, lap in enumerate(raw_laps):
        dist_km = (lap.get("distance") or 0) / 1000
        dur_min = (lap.get("duration") or 0) / 60
        rows.append({
            "activity_id": activity_id,
            "lap_index": i,
            "distance_km": round(dist_km, 3),
            "duration_min": round(dur_min, 3),
            "pace_min_km": _pace(dist_km, dur_min),
            "avg_hr": _int(lap.get("averageHR")),
            "avg_cadence": _r(lap.get("averageRunningCadenceInStepsPerMinute"), 0),
            "elevation_gain_m": _r(lap.get("elevationGain"), 1),
        })
    return rows


# --------------------------------------------------------------------------- #
# Daily summary
# --------------------------------------------------------------------------- #

def to_daily_summary(
    raw: dict,
    rhr_by_date: dict[str, int],
    stress_by_date: dict[str, int],
    bb_by_date: dict[str, dict],
) -> dict:
    """Raw daily summary dict → normalized daily_summary row."""
    d = raw.get("_date") or (raw.get("calendarDate") or "")[:10]
    bb = bb_by_date.get(d, {})
    return {
        "date": d,
        "steps": _int(raw.get("totalSteps")),
        "calories_total": _int(raw.get("totalKilocalories")),
        "calories_active": _int(raw.get("activeKilocalories")),
        "resting_hr": rhr_by_date.get(d),
        "stress_avg": stress_by_date.get(d),
        "body_battery_min": _int(bb.get("min")),
        "body_battery_max": _int(bb.get("max")),
        "intensity_minutes_moderate": _int(raw.get("moderateIntensityMinutes")),
        "intensity_minutes_vigorous": _int(raw.get("vigorousIntensityMinutes")),
        "floors_ascended": _r(raw.get("floorsAscended"), 1),
        "respiration_avg": _r(raw.get("avgWakingRespirationValue"), 1),
        "spo2_avg": _r(raw.get("averageSpO2Value"), 1),
    }


# --------------------------------------------------------------------------- #
# Sleep
# --------------------------------------------------------------------------- #

def to_sleep(raw: dict) -> dict | None:
    """Raw sleep data dict → normalized sleep row. Returns None if no date found."""
    # Garmin nests sleep data under 'dailySleepDTO' on most firmware versions
    dto = raw.get("dailySleepDTO") or raw
    d = raw.get("_date") or (dto.get("calendarDate") or "")[:10]
    if not d:
        return None

    # sleepScores may be a nested dict or a flat integer depending on device
    sleep_scores = dto.get("sleepScores")
    if isinstance(sleep_scores, dict):
        overall = sleep_scores.get("overall")
        score = _int(overall.get("value") if isinstance(overall, dict) else overall)
    else:
        score = _int(dto.get("sleepScore"))

    def _secs_to_min(key: str) -> int | None:
        v = dto.get(key)
        return _int(v / 60) if v else None

    return {
        "date": d,
        "total_min": _secs_to_min("sleepTimeSeconds"),
        "deep_min": _secs_to_min("deepSleepSeconds"),
        "light_min": _secs_to_min("lightSleepSeconds"),
        "rem_min": _secs_to_min("remSleepSeconds"),
        "awake_min": _secs_to_min("awakeSleepSeconds"),
        "sleep_score": score,
        "avg_overnight_hr": _r(dto.get("averageSpO2HRSleep"), 1),
        "avg_hrv": _r(dto.get("avgSleepStress"), 1),
    }


# --------------------------------------------------------------------------- #
# HRV
# --------------------------------------------------------------------------- #

def to_hrv(raw: dict) -> dict | None:
    """Raw HRV data → normalized hrv row. Returns None if no date."""
    d = raw.get("_date")
    if not d:
        return None
    # HRV summary nesting varies by device/firmware
    hrv_summary = raw.get("hrvSummary") or raw
    return {
        "date": d,
        "last_night_avg": _r(hrv_summary.get("lastNight"), 1),
        "weekly_avg": _r(hrv_summary.get("weeklyAvg"), 1),
        "status": _str(hrv_summary.get("status")),
    }


# --------------------------------------------------------------------------- #
# Training
# --------------------------------------------------------------------------- #

def to_training(raw: dict) -> dict | None:
    """Raw training + readiness + max_metrics → normalized training row."""
    d = raw.get("_date")
    if not d:
        return None

    status_data = raw.get("_status") or {}
    readiness_data = raw.get("_readiness") or {}
    max_metrics_data = raw.get("_max_metrics") or {}

    # Training status nesting varies
    ts = status_data.get("trainingStatusDTO") or status_data

    # Training readiness nesting varies
    tr = readiness_data.get("trainingReadinessDTO") or readiness_data

    # VO2max from max_metrics
    vo2max: float | None = None
    if isinstance(max_metrics_data, dict):
        vo2max = (
            _r(max_metrics_data.get("vo2MaxPreciseValue"), 1)
            or _r((max_metrics_data.get("generic") or {}).get("vo2MaxPreciseValue"), 1)
        )

    return {
        "date": d,
        "vo2max": vo2max,
        "training_status": _str(
            ts.get("trainingStatus") or ts.get("latestTrainingStatusPhase")
        ),
        "acute_load": _r(ts.get("acuteLoad"), 1),
        "chronic_load": _r(
            ts.get("chronicLoad")
            or (ts.get("metricData") or {}).get("trainingLoad7"),
            1,
        ),
        "training_readiness_score": _int(tr.get("score")),
        "training_readiness_description": _str(
            tr.get("levelDescription") or tr.get("description")
        ),
    }


# --------------------------------------------------------------------------- #
# Personal records
# --------------------------------------------------------------------------- #

def to_personal_record(raw: dict) -> dict:
    return {
        "record_id": _int(raw.get("id")),
        "type_id": _int(raw.get("typeId")),
        "type_key": _str(raw.get("typeKey")),
        "activity_id": _int(raw.get("activityId")),
        "value": _r(raw.get("value"), 3),
        "date": (raw.get("updateDate") or "")[:10],
    }
