import socket
import subprocess
import sys
import time
from collections.abc import Iterator

import httpx
import pytest

SERVER_START_TIMEOUT_SECONDS = 20
HEALTH_POLL_INTERVAL_SECONDS = 0.1


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_until_healthy(base_url: str) -> None:
    deadline = time.monotonic() + SERVER_START_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        try:
            if httpx.get(f"{base_url}/api/health").status_code == 200:
                return
        except httpx.TransportError:
            pass
        time.sleep(HEALTH_POLL_INTERVAL_SECONDS)
    raise RuntimeError(f"Server at {base_url} did not become healthy")


@pytest.fixture(scope="session")
def base_url() -> Iterator[str]:
    port = _free_port()
    url = f"http://127.0.0.1:{port}"
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port)],
    )
    try:
        _wait_until_healthy(url)
        yield url
    finally:
        server.terminate()
        server.wait()
