from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.banking.client import EnableBankingClient
from app.tls import generate_private_key, write_private_key
from tests.fakes.enable_banking import FakeBankState, create_fake_enable_banking

TEST_APP_ID = "test-app-id"


@pytest.fixture(scope="session")
def private_key() -> RSAPrivateKey:
    return generate_private_key()


@pytest.fixture
def key_file(tmp_path: Path, private_key: RSAPrivateKey) -> Path:
    path = tmp_path / "key.pem"
    write_private_key(private_key, path)
    return path


@pytest.fixture
def fake_enable_banking() -> FastAPI:
    return create_fake_enable_banking()


@pytest.fixture
def fake_bank(fake_enable_banking: FastAPI) -> FakeBankState:
    return fake_enable_banking.state.bank


@pytest.fixture
def bank_client(fake_enable_banking: FastAPI, key_file: Path) -> EnableBankingClient:
    return EnableBankingClient(
        http=TestClient(fake_enable_banking), app_id=TEST_APP_ID, key_path=key_file
    )
