"""The OAuth `state` sent to Enable Banking: "<local port>.<nonce>".

The port lets the hosted production callback page relay the bank's answer back to this machine;
site/callback.html keeps a copy of STATE_PATTERN (checked by tests/unit/test_site.py)."""

import secrets

STATE_PATTERN = r"^\d{1,5}\.[A-Za-z0-9_-]{16,128}$"


def new_state(port: int) -> tuple[str, str]:
    nonce = secrets.token_urlsafe(24)
    return f"{port}.{nonce}", nonce


def nonce_of(state: str) -> str:
    return state.partition(".")[2]
