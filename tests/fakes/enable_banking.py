"""In-memory stand-in for the Enable Banking API, used by unit tests (via TestClient) and e2e
tests (served by uvicorn). Only the endpoints Yiji calls are implemented."""

from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any
from urllib.parse import urlencode

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

FAKE_CODE = "fake-authorization-code"
FAKE_ACCOUNT_UID = "fake-account"
FAKE_ACCOUNT_HASH = "fake-account-hash"
SESSION_VALID_UNTIL = "2099-01-01T00:00:00+00:00"


def debit(
    amount: str,
    booking_date: date,
    *,
    currency: str = "EUR",
    creditor: str | None = None,
    creditor_iban: str | None = None,
    remittance: list[str] | None = None,
    family: str | None = None,
    sub_family: str | None = None,
    status: str = "BOOK",
    indicator: str = "DBIT",
) -> dict[str, Any]:
    transaction: dict[str, Any] = {
        "transaction_amount": {"amount": amount, "currency": currency},
        "credit_debit_indicator": indicator,
        "status": status,
        "booking_date": booking_date.isoformat(),
        "remittance_information": remittance or [],
    }
    if creditor is not None:
        transaction["creditor"] = {"name": creditor}
    if creditor_iban is not None:
        transaction["creditor_account"] = {"iban": creditor_iban}
    if family or sub_family:
        transaction["bank_transaction_code"] = {"code": family, "sub_code": sub_family}
    return transaction


class FakeBankConfig(BaseModel):
    transactions: list[dict[str, Any]] = []
    accounts: list[dict[str, Any]] = [
        {"uid": FAKE_ACCOUNT_UID, "identification_hash": FAKE_ACCOUNT_HASH}
    ]
    """Every account serves the same transactions."""
    page_size: int = 100
    session_valid_until: str = SESSION_VALID_UNTIL
    deny_access: bool = False
    session_expired: bool = False
    failure_status: int | None = None
    history_from: str | None = None
    """Earliest `date_from` the bank serves; older requests are refused, as banks limit history."""


class FakeBankState(FakeBankConfig):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    requests: list[Request] = []
    auth_bodies: list[dict[str, Any]] = []


def create_fake_enable_banking() -> FastAPI:
    fake = FastAPI()
    fake.state.bank = FakeBankState()

    def bank() -> FakeBankState:
        return fake.state.bank

    @fake.middleware("http")
    async def record(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        bank().requests.append(request)
        failure_status = bank().failure_status
        if failure_status is not None and not request.url.path.startswith("/_fake"):
            return JSONResponse({"message": "fake failure"}, status_code=failure_status)
        return await call_next(request)

    @fake.post("/auth")
    def start_authorization(body: dict[str, Any]) -> dict[str, str]:
        bank().auth_bodies.append(body)
        if bank().deny_access:
            query = {"error": "access_denied", "state": body["state"]}
        else:
            query = {"code": FAKE_CODE, "state": body["state"]}
        return {"url": f"{body['redirect_url']}?{urlencode(query)}"}

    @fake.post("/sessions")
    def create_session(body: dict[str, Any]) -> dict[str, Any]:
        if body.get("code") != FAKE_CODE:
            raise HTTPException(status_code=422, detail="invalid code")
        return {
            "session_id": "fake-session",
            "accounts": bank().accounts,
            "access": {"valid_until": bank().session_valid_until},
        }

    @fake.get("/accounts/{account_uid}/transactions", response_model=None)
    def transactions(
        account_uid: str, date_from: str, continuation_key: str | None = None
    ) -> dict[str, Any] | JSONResponse:
        if bank().session_expired:
            return JSONResponse(
                {"code": 401, "message": "Session expired", "error": "EXPIRED_SESSION"},
                status_code=401,
            )
        history_from = bank().history_from
        if history_from and date_from < history_from:
            return JSONResponse(
                {"code": 422, "message": "Too old", "error": "WRONG_TRANSACTIONS_PERIOD"},
                status_code=422,
            )
        start = int(continuation_key or 0)
        end = start + bank().page_size
        matching = [
            transaction
            for transaction in bank().transactions
            if (transaction.get("booking_date") or "") >= date_from
        ]
        return {
            "transactions": matching[start:end],
            "continuation_key": str(end) if end < len(matching) else None,
        }

    @fake.post("/_fake/configure")
    def configure(config: FakeBankConfig) -> None:
        fake.state.bank = FakeBankState(**config.model_dump())

    return fake
