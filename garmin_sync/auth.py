"""
auth.py — Garmin Connect authentication.

Prefers GARMIN_TOKEN (base64-encoded garth session) so MFA accounts work on CI.
Falls back to GARMIN_EMAIL + GARMIN_PASSWORD for first-time token generation.

To generate a token locally for the first time:
    python -c "
    from garminconnect import Garmin
    c = Garmin('you@example.com', 'yourpassword')
    c.login()
    print(c.garth.dumps())
    "
Then store the output as the GARMIN_TOKEN secret in GitHub Actions.
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

    client = Garmin(email or "", password or "")

    if token:
        try:
            client.garth.loads(token)
            client.garth.refresh_oauth2()
            return client
        except Exception:
            pass  # fall through to email/password login

    client.login()
    return client
