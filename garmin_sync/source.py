"""
source.py — Ingestion boundary abstraction.

GarminSource is the Protocol all data providers must satisfy.
GarminConnectSource wraps the unofficial garminconnect library — it is the
only module that imports garminconnect directly. Swap this implementation
here if the official Garmin Developer API becomes viable, or to add a
FIT-file importer, without touching the rest of the pipeline.
"""
from __future__ import annotations

from typing import Protocol

from garminconnect import Garmin


class GarminSource(Protocol):
    """Protocol for Garmin data providers."""

    def get_activities(self, start: str, end: str) -> list[dict]: ...
    def get_activity_laps(self, activity_id: int) -> list[dict]: ...
    def get_activity_hr_zones(self, activity_id: int) -> list[dict]: ...
    def get_daily_summary(self, date: str) -> dict: ...
    def get_rhr(self, start: str, end: str) -> list[dict]: ...
    def get_stress(self, date: str) -> dict: ...
    def get_body_battery(self, start: str, end: str) -> list[dict]: ...
    def get_sleep(self, date: str) -> dict: ...
    def get_hrv(self, date: str) -> dict: ...
    def get_training_readiness(self, date: str) -> dict: ...
    def get_training_status(self, date: str) -> dict: ...
    def get_max_metrics(self, date: str) -> dict: ...
    def get_personal_records(self) -> list[dict]: ...


class GarminConnectSource:
    """GarminSource backed by the unofficial garminconnect / garth library."""

    def __init__(self, client: Garmin) -> None:
        self._c = client

    def get_activities(self, start: str, end: str) -> list[dict]:
        return self._c.get_activities_by_date(start, end, activitytype="running") or []

    def get_activity_laps(self, activity_id: int) -> list[dict]:
        try:
            result = self._c.get_activity_split_summaries(activity_id)
            # Returns dict with 'lapDTOs' list on most firmware versions
            if isinstance(result, dict):
                return result.get("lapDTOs") or []
            return result or []
        except Exception:
            return []

    def get_activity_hr_zones(self, activity_id: int) -> list[dict]:
        try:
            return self._c.get_activity_hr_in_timezones(activity_id) or []
        except Exception:
            return []

    def get_daily_summary(self, date: str) -> dict:
        try:
            return self._c.get_user_summary(date) or {}
        except Exception:
            return {}

    def get_rhr(self, start: str, end: str) -> list[dict]:
        try:
            return self._c.get_rhr_day(start, end) or []
        except Exception:
            return []

    def get_stress(self, date: str) -> dict:
        try:
            return self._c.get_stress_data(date) or {}
        except Exception:
            return {}

    def get_body_battery(self, start: str, end: str) -> list[dict]:
        try:
            return self._c.get_body_battery(start, end) or []
        except Exception:
            return []

    def get_sleep(self, date: str) -> dict:
        try:
            return self._c.get_sleep_data(date) or {}
        except Exception:
            return {}

    def get_hrv(self, date: str) -> dict:
        try:
            return self._c.get_hrv_data(date) or {}
        except Exception:
            return {}

    def get_training_readiness(self, date: str) -> dict:
        try:
            result = self._c.get_training_readiness(date) or {}
            if isinstance(result, list):
                return result[0] if result else {}
            return result
        except Exception:
            return {}

    def get_training_status(self, date: str) -> dict:
        try:
            result = self._c.get_training_status(date) or {}
            if isinstance(result, list):
                return result[0] if result else {}
            return result
        except Exception:
            return {}

    def get_max_metrics(self, date: str) -> dict:
        try:
            result = self._c.get_max_metrics(date) or {}
            if isinstance(result, list):
                return result[0] if result else {}
            return result
        except Exception:
            return {}

    def get_personal_records(self) -> list[dict]:
        try:
            return self._c.get_personal_record() or []
        except Exception:
            return []
