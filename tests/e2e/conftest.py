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

from app.categories import CategoryBook, CategoryStore
from app.modules import DataFiles
from app.tls import generate_private_key, write_private_key

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


def loopback_origin(port: int) -> str:
    return f"http://127.0.0.1:{port}"


@pytest.fixture(scope="session")
def servers() -> Iterator[list[subprocess.Popen[bytes]]]:
    started: list[subprocess.Popen[bytes]] = []
    yield started
    for server in started:
        server.terminate()
        server.wait()


@pytest.fixture(scope="session")
def serve_app(servers: list[subprocess.Popen[bytes]]) -> AppServer:
    def start(
        port: int, data_dir: Path, env: dict[str, str], tls: tuple[Path, Path] | None = None
    ) -> str:
        app_env = {"YIJI_PORT": str(port), "YIJI_DATA_DIR": str(data_dir), **env}
        if tls is None:
            origin, tls_args = loopback_origin(port), ()
        else:
            certificate, key = tls
            origin = f"https://localhost:{port}"
            tls_args = ("--ssl-certfile", str(certificate), "--ssl-keyfile", str(key))
        servers.append(_serve("app.main:app", origin, "/api/health", app_env, *tls_args))
        return origin

    return start


@pytest.fixture(scope="session")
def fake_bank_url(servers: list[subprocess.Popen[bytes]]) -> str:
    origin = loopback_origin(free_port())
    fake_app = "tests.fakes.enable_banking:create_fake_enable_banking"
    servers.append(_serve(fake_app, origin, "/docs", {}, "--factory"))
    return origin


@pytest.fixture(scope="session")
def fake_rates_url(servers: list[subprocess.Popen[bytes]]) -> str:
    origin = loopback_origin(free_port())
    fake_app = "tests.fakes.exchange_rates:create_fake_exchange_rates"
    servers.append(_serve(fake_app, origin, "/docs", {}, "--factory"))
    return origin


@pytest.fixture(scope="session")
def fake_ollama_url(servers: list[subprocess.Popen[bytes]]) -> str:
    origin = loopback_origin(free_port())
    fake_app = "tests.fakes.ollama:create_fake_ollama"
    servers.append(_serve(fake_app, origin, "/docs", {}, "--factory"))
    return origin


@pytest.fixture(scope="session")
def test_key_file(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("keys") / "key.pem"
    write_private_key(generate_private_key(), path)
    return path


@pytest.fixture(scope="session")
def app_data_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("yiji-data")


@pytest.fixture(scope="session")
def base_url(
    serve_app: AppServer,
    fake_bank_url: str,
    fake_rates_url: str,
    fake_ollama_url: str,
    test_key_file: Path,
    app_data_dir: Path,
) -> str:
    port = free_port()
    url = loopback_origin(port)
    return serve_app(
        port,
        app_data_dir,
        {
            "YIJI_ENABLE_BANKING_ENVIRONMENT": "sandbox",
            "YIJI_ENABLE_BANKING_API_URL": fake_bank_url,
            "YIJI_EXCHANGE_RATES_API_URL": fake_rates_url,
            "YIJI_OLLAMA_API_URL": fake_ollama_url,
            "OLLAMA_API_KEY": "e2e-ollama-key",
            "YIJI_ENABLE_BANKING_SANDBOX_REDIRECT_URL": f"{url}/callback",
            "ENABLE_BANKING_SANDBOX_ID": "e2e-sandbox-app",
            "ENABLE_BANKING_SANDBOX_KEY_PATH": str(test_key_file),
        },
    )


@pytest.fixture
def fake_rates(fake_rates_url: str) -> Callable[..., None]:
    """Resets the fake exchange rate service; call it to seed rates."""

    def configure(**config: Any) -> None:
        httpx2.post(f"{fake_rates_url}/_fake/configure", json=config).raise_for_status()

    configure()
    return configure


@pytest.fixture
def fake_ollama(fake_ollama_url: str) -> Callable[..., None]:
    """Resets the fake Ollama model; call it to set its answers."""

    def configure(**config: Any) -> None:
        httpx2.post(f"{fake_ollama_url}/_fake/configure", json=config).raise_for_status()

    configure()
    return configure


@pytest.fixture
def fake_bank(
    fake_bank_url: str, fake_rates: Callable[..., None], app_data_dir: Path
) -> Callable[..., None]:
    """Resets the fake bank and the app's stored connection, history, rates and categories;
    call it to seed bank data."""

    def configure(**config: Any) -> None:
        httpx2.post(f"{fake_bank_url}/_fake/configure", json=config).raise_for_status()

    configure()
    files = DataFiles.under(app_data_dir)
    for path in (files.bank, files.categories, files.database):
        path.unlink(missing_ok=True)
    for journal in app_data_dir.glob(f"{files.database.name}-*"):
        journal.unlink()
    return configure


@pytest.fixture
def seed_categories(
    fake_bank: Callable[..., None], app_data_dir: Path
) -> Callable[[dict[str, list[str]]], None]:
    """Stores categories, each with the counterparty names assigned to it."""

    def seed(assignments: dict[str, list[str]]) -> None:
        book = CategoryBook()
        for name, counterparties in assignments.items():
            category = book.create(name)
            for counterparty in counterparties:
                book.assign(counterparty, category.id)
        CategoryStore(DataFiles.under(app_data_dir).categories, []).save(book)

    return seed
