"""
auth.py — Garmin Connect authentication.

Prefers GARMIN_TOKEN (JSON from c.client.dumps()) so MFA accounts work on CI.
Falls back to GARMIN_EMAIL + GARMIN_PASSWORD for first-time token generation.

To generate a token locally (run get_token.py, copy its output):
    py -3.12 get_token.py
Store the output as the GARMIN_TOKEN secret in GitHub Actions.
"""
from __future__ import annotations

import os

from garminconnect import Garmin


def get_client() -> Garmin:
    """Return an authenticated Garmin Connect client."""
    email = os.getenv("GARMIN_EMAIL")
    password = os.getenv("GARMIN_PASSWORD")
    token = os.getenv("GARMIN_TOKEN")

    if not (email and password) and not token:
        raise SystemExit(
            "Credentials missing. Set GARMIN_EMAIL + GARMIN_PASSWORD "
            "(first run / local) or GARMIN_TOKEN (CI / MFA accounts)."
        )

    if token:
        # garminconnect 0.3.6 uses its own client.Client (not garth).
        # Token is JSON: {"di_token": ..., "di_refresh_token": ..., "di_client_id": ...}
        # Load directly into the internal client to bypass login()'s >512 path heuristic.
        client = Garmin()
        client.client.loads(token)
        return client

    if not (email and password):
        raise SystemExit("No token and no GARMIN_EMAIL/GARMIN_PASSWORD set.")

    client = Garmin(email, password)
    client.login()
    return client
