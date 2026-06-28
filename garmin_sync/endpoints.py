"""
endpoints.py — Domain-grouped data fetching via a GarminSource.

Each function returns raw data from the source with minimal processing.
Normalization to schema rows is the job of transform.py.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from .source import GarminSource

log = logging.getLogger(__name__)


def fetch_activities(source: GarminSource, start: str, end: str) -> list[dict]:
    """Fetch running activities with distance > 0."""
    log.info("Fetching activities %s → %s", start, end)
    activities = source.get_activities(start, end)
    log.info("  %d raw activities, filtering for distance > 0", len(activities))
    return [a for a in activities if (a.get("distance") or 0) > 0]


def fetch_activity_laps(source: GarminSource, activity_id: int) -> list[dict]:
    return source.get_activity_laps(activity_id)


def fetch_activity_hr_zones(source: GarminSource, activity_id: int) -> list[dict]:
    return source.get_activity_hr_zones(activity_id)


def fetch_daily_summaries(source: GarminSource, start: str, end: str) -> list[dict]:
    """Fetch daily user summary for each date in [start, end]."""
    log.info("Fetching daily summaries %s → %s", start, end)
    results = []
    current = date.fromisoformat(start)
    stop = date.fromisoformat(end)
    while current <= stop:
        d = current.isoformat()
        data = source.get_daily_summary(d)
        if data:
            data["_date"] = d
            results.append(data)
        current += timedelta(days=1)
    log.info("  %d daily summaries fetched", len(results))
    return results


def fetch_rhr(source: GarminSource, start: str, end: str) -> list[dict]:
    log.info("Fetching resting HR %s → %s", start, end)
    return source.get_rhr(start, end)


def fetch_stress(source: GarminSource, start: str, end: str) -> list[dict]:
    """Fetch daily stress for each date in [start, end]."""
    log.info("Fetching stress %s → %s", start, end)
    results = []
    current = date.fromisoformat(start)
    stop = date.fromisoformat(end)
    while current <= stop:
        d = current.isoformat()
        data = source.get_stress(d)
        if data:
            data["_date"] = d
            results.append(data)
        current += timedelta(days=1)
    return results


def fetch_body_battery(source: GarminSource, start: str, end: str) -> list[dict]:
    log.info("Fetching body battery %s → %s", start, end)
    return source.get_body_battery(start, end)


def fetch_sleep(source: GarminSource, start: str, end: str) -> list[dict]:
    """Fetch sleep data for each date in [start, end]."""
    log.info("Fetching sleep %s → %s", start, end)
    results = []
    current = date.fromisoformat(start)
    stop = date.fromisoformat(end)
    while current <= stop:
        d = current.isoformat()
        data = source.get_sleep(d)
        if data:
            data["_date"] = d
            results.append(data)
        current += timedelta(days=1)
    log.info("  %d sleep records fetched", len(results))
    return results


def fetch_hrv(source: GarminSource, start: str, end: str) -> list[dict]:
    """Fetch HRV data for each date in [start, end]."""
    log.info("Fetching HRV %s → %s", start, end)
    results = []
    current = date.fromisoformat(start)
    stop = date.fromisoformat(end)
    while current <= stop:
        d = current.isoformat()
        data = source.get_hrv(d)
        if data:
            data["_date"] = d
            results.append(data)
        current += timedelta(days=1)
    return results


def fetch_training(source: GarminSource, start: str, end: str) -> list[dict]:
    """Fetch training status, readiness, and VO2max for each date in [start, end]."""
    log.info("Fetching training metrics %s → %s", start, end)
    results = []
    current = date.fromisoformat(start)
    stop = date.fromisoformat(end)
    while current <= stop:
        d = current.isoformat()
        entry: dict = {"_date": d}
        status = source.get_training_status(d)
        readiness = source.get_training_readiness(d)
        max_metrics = source.get_max_metrics(d)
        if status:
            entry["_status"] = status
        if readiness:
            entry["_readiness"] = readiness
        if max_metrics:
            entry["_max_metrics"] = max_metrics
        if len(entry) > 1:  # has at least one data source
            results.append(entry)
        current += timedelta(days=1)
    return results


def fetch_personal_records(source: GarminSource) -> list[dict]:
    log.info("Fetching personal records")
    return source.get_personal_records()
