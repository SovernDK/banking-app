from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path

import httpx2
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

from app.banking.client import BankApiError, BankSessionExpiredError, EnableBankingClient
from tests.fakes.enable_banking import FAKE_ACCOUNT_UID, FAKE_CODE, FakeBankState, debit
from tests.unit.conftest import TEST_APP_ID

VALID_UNTIL = datetime(2027, 1, 1, tzinfo=UTC)


def _start(bank_client: EnableBankingClient) -> str:
    return bank_client.start_authorization(
        aspsp_name="Mock ASPSP",
        aspsp_country="FI",
        redirect_url="https://example.test/callback.html",
        state="8100.nonce",
        valid_until=VALID_UNTIL,
    )


def test_requests_are_signed_with_app_key_as_rs256_jwt(
    bank_client: EnableBankingClient, fake_bank: FakeBankState, private_key: RSAPrivateKey
) -> None:
    _start(bank_client)

    token = fake_bank.requests[-1].headers["authorization"].removeprefix("Bearer ")
    claims = jwt.decode(
        token, private_key.public_key(), algorithms=["RS256"], audience="api.enablebanking.com"
    )
    assert jwt.get_unverified_header(token)["kid"] == TEST_APP_ID
    assert claims["iss"] == "enablebanking.com"
    assert claims["exp"] > claims["iat"]


def test_start_authorization_returns_bank_url_and_sends_consent_details(
    bank_client: EnableBankingClient, fake_bank: FakeBankState
) -> None:
    url = _start(bank_client)

    assert url == f"https://example.test/callback.html?code={FAKE_CODE}&state=8100.nonce"
    assert fake_bank.auth_bodies[-1] == {
        "access": {"valid_until": VALID_UNTIL.isoformat()},
        "aspsp": {"name": "Mock ASPSP", "country": "FI"},
        "state": "8100.nonce",
        "redirect_url": "https://example.test/callback.html",
        "psu_type": "personal",
    }


def test_create_session_returns_accounts(bank_client: EnableBankingClient) -> None:
    session = bank_client.create_session(FAKE_CODE)

    assert [account.uid for account in session.accounts] == [FAKE_ACCOUNT_UID]


def test_fetch_transactions_follows_continuation_keys(
    bank_client: EnableBankingClient, fake_bank: FakeBankState
) -> None:
    fake_bank.transactions = [debit(str(index), date(2026, 11, 10)) for index in range(1, 6)]
    fake_bank.page_size = 2

    transactions = bank_client.fetch_transactions(FAKE_ACCOUNT_UID, date(2026, 11, 1))

    assert [transaction.transaction_amount.amount for transaction in transactions] == [
        1,
        2,
        3,
        4,
        5,
    ]


def test_server_error_raises_bank_api_error(
    bank_client: EnableBankingClient, fake_bank: FakeBankState
) -> None:
    fake_bank.failure_status = 500

    with pytest.raises(BankApiError):
        bank_client.create_session(FAKE_CODE)


def test_malformed_response_raises_bank_api_error(
    bank_client: EnableBankingClient, fake_bank: FakeBankState
) -> None:
    fake_bank.transactions = [
        {**debit("1", date(2026, 11, 10)), "credit_debit_indicator": "SIDEWAYS"}
    ]

    with pytest.raises(BankApiError):
        bank_client.fetch_transactions(FAKE_ACCOUNT_UID, date(2026, 11, 1))


def _client_answering(
    handler: Callable[[httpx2.Request], httpx2.Response], key_file: Path
) -> EnableBankingClient:
    http = httpx2.Client(base_url="https://bank.test", transport=httpx2.MockTransport(handler))
    return EnableBankingClient(http=http, app_id=TEST_APP_ID, key_path=key_file)


def test_network_failure_raises_bank_api_error(key_file: Path) -> None:
    def refuse(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("refused", request=request)

    with pytest.raises(BankApiError):
        _client_answering(refuse, key_file).create_session(FAKE_CODE)


@pytest.mark.parametrize(
    ("status", "body", "session_ended"),
    [
        # Session error codes from https://enablebanking.com/docs/api/reference/ (ErrorCode).
        (401, b'{"code": 401, "error": "EXPIRED_SESSION"}', True),
        (401, b'{"code": 401, "error": "CLOSED_SESSION"}', True),
        (401, b'{"code": 401, "error": "REVOKED_SESSION"}', True),
        (404, b'{"code": 404, "error": "SESSION_DOES_NOT_EXIST"}', True),
        (401, b'{"code": 401, "error": "UNAUTHORIZED_ACCESS"}', False),
        (403, b'{"code": 403, "error": "ACCESS_DENIED"}', False),
        (401, b'{"code": 401, "error": ""}', False),
        (401, b'{"code": 401}', False),
        (401, b'{"code": 401, "error": ["EXPIRED_SESSION"]}', False),
        (401, b'["EXPIRED_SESSION"]', False),
        (401, b"<html>EXPIRED_SESSION</html>", False),
    ],
)
def test_only_session_error_codes_are_treated_as_an_ended_bank_session(
    key_file: Path, status: int, body: bytes, session_ended: bool
) -> None:
    """Any other refusal, e.g. a rejected app key, must not wipe the user's stored bank session."""

    def refuse(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(status, content=body)

    with pytest.raises(BankApiError) as raised:
        _client_answering(refuse, key_file).fetch_transactions(FAKE_ACCOUNT_UID, date(2026, 11, 1))
    assert isinstance(raised.value, BankSessionExpiredError) is session_ended
