import os
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, Protocol

import httpx2
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

SERVER_START_TIMEOUT_SECONDS = 20
HEALTH_POLL_INTERVAL_SECONDS = 0.1


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_until_up(url: str) -> None:
    deadline = time.monotonic() + SERVER_START_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        try:
            # Local servers may use a self-signed certificate.
            if httpx2.get(url, verify=False).status_code < 500:
                return
        except httpx2.TransportError:
            pass
        time.sleep(HEALTH_POLL_INTERVAL_SECONDS)
    raise RuntimeError(f"Server at {url} did not come up")


def _serve(
    target: str, origin: str, health_path: str, env: dict[str, str], *uvicorn_args: str
) -> subprocess.Popen[bytes]:
    port = origin.rsplit(":", 1)[1]
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", target, "--port", port, *uvicorn_args],
        env={**os.environ, **env},
    )
    try:
        _wait_until_up(f"{origin}{health_path}")
    except RuntimeError:
        server.terminate()
        raise
    return server


class AppServer(Protocol):
    def __call__(
        self, port: int, data_dir: Path, env: dict[str, str], tls: tuple[Path, Path] | None = None
    ) -> str: ...


@pytest.fixture(scope="session")
def serve_app() -> Iterator[AppServer]:
    servers: list[subprocess.Popen[bytes]] = []

    def start(
        port: int, data_dir: Path, env: dict[str, str], tls: tuple[Path, Path] | None = None
    ) -> str:
        app_env = {"YIJI_PORT": str(port), "YIJI_DATA_DIR": str(data_dir), **env}
        if tls is None:
            origin, tls_args = f"http://127.0.0.1:{port}", ()
        else:
            certificate, key = tls
            origin = f"https://localhost:{port}"
            tls_args = ("--ssl-certfile", str(certificate), "--ssl-keyfile", str(key))
        servers.append(_serve("app.main:app", origin, "/api/health", app_env, *tls_args))
        return origin

    yield start
    for server in servers:
        server.terminate()
        server.wait()


@pytest.fixture(scope="session")
def fake_bank_url() -> Iterator[str]:
    port = free_port()
    server = _serve(
        "tests.fakes.enable_banking:create_fake_enable_banking",
        f"http://127.0.0.1:{port}",
        "/docs",
        {},
        "--factory",
    )
    yield f"http://127.0.0.1:{port}"
    server.terminate()
    server.wait()


@pytest.fixture(scope="session")
def test_key_file(tmp_path_factory: pytest.TempPathFactory) -> Path:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    path = tmp_path_factory.mktemp("keys") / "key.pem"
    path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return path


@pytest.fixture(scope="session")
def app_data_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("yiji-data")


@pytest.fixture(scope="session")
def base_url(
    serve_app: AppServer, fake_bank_url: str, test_key_file: Path, app_data_dir: Path
) -> str:
    port = free_port()
    url = f"http://127.0.0.1:{port}"
    return serve_app(
        port,
        app_data_dir,
        {
            "YIJI_ENABLE_BANKING_ENVIRONMENT": "sandbox",
            "YIJI_ENABLE_BANKING_API_URL": fake_bank_url,
            "YIJI_ENABLE_BANKING_SANDBOX_REDIRECT_URL": f"{url}/callback",
            "ENABLE_BANKING_SANDBOX_ID": "e2e-sandbox-app",
            "ENABLE_BANKING_SANDBOX_KEY_PATH": str(test_key_file),
        },
    )


@pytest.fixture
def fake_bank(fake_bank_url: str, app_data_dir: Path) -> Callable[..., None]:
    """Resets the fake bank and the app's stored connection; call it to seed bank data."""

    def configure(**config: Any) -> None:
        httpx2.post(f"{fake_bank_url}/_fake/configure", json=config).raise_for_status()

    configure()
    (app_data_dir / "bank.json").unlink(missing_ok=True)
    return configure
