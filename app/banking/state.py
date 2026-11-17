"""The OAuth `state` sent to Enable Banking: "<target>.<nonce>".

The target tells the hosted production callback page where to relay the bank's answer: the local
port when Yiji runs on the viewer's machine, or Yiji's own https origin (base64url) when it runs on
a server. site/callback.html keeps a copy of STATE_PATTERN (checked by tests/unit/test_site.py)."""

import base64
import secrets

STATE_PATTERN = r"^(\d{1,5}|[A-Za-z0-9_-]{8,400})\.[A-Za-z0-9_-]{16,128}$"


def new_state(port: int, public_origin: str | None = None) -> tuple[str, str]:
    nonce = secrets.token_urlsafe(24)
    if public_origin is None:
        target = str(port)
    else:
        target = base64.urlsafe_b64encode(public_origin.encode()).decode().rstrip("=")
    return f"{target}.{nonce}", nonce


def nonce_of(state: str) -> str:
    return state.partition(".")[2]
