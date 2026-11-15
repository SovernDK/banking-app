"""In-memory stand-in for the Enable Banking API, used by unit tests (via TestClient) and e2e
tests (served by uvicorn). Only the endpoints Yiji calls are implemented."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

FAKE_CODE = "fake-authorization-code"
FAKE_SESSION_ID = "fake-session"
FAKE_ACCOUNT_UID = "fake-account"


@dataclass
class FakeBankState:
    transactions: list[dict[str, Any]] = field(default_factory=list)
    page_size: int = 100
    deny_access: bool = False
    session_expired: bool = False
    failure_status: int | None = None
    requests: list[Request] = field(default_factory=list)
    tokens: list[str] = field(default_factory=list)
    auth_bodies: list[dict[str, Any]] = field(default_factory=list)


class FakeBankConfig(BaseModel):
    transactions: list[dict[str, Any]] = []
    page_size: int = 100
    deny_access: bool = False
    session_expired: bool = False
    failure_status: int | None = None


def create_fake_enable_banking(valid_until: str = "2099-01-01T00:00:00+00:00") -> FastAPI:
    fake = FastAPI()
    fake.state.bank = FakeBankState()

    def bank() -> FakeBankState:
        return fake.state.bank

    @fake.middleware("http")
    async def record(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        bank().requests.append(request)
        authorization = request.headers.get("authorization", "")
        if authorization.startswith("Bearer "):
            bank().tokens.append(authorization.removeprefix("Bearer "))
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
        return {"url": f"{body['redirect_url']}?{urlencode(query)}", "authorization_id": "auth-1"}

    @fake.post("/sessions")
    def create_session(body: dict[str, Any]) -> dict[str, Any]:
        if body.get("code") != FAKE_CODE:
            raise HTTPException(status_code=422, detail="invalid code")
        return {
            "session_id": FAKE_SESSION_ID,
            "accounts": [{"uid": FAKE_ACCOUNT_UID, "currency": "EUR"}],
            "access": {"valid_until": valid_until},
        }

    @fake.get("/accounts/{account_uid}/transactions")
    def transactions(
        account_uid: str,
        date_from: str,
        continuation_key: str | None = None,
        authorization: str = Header(),
    ) -> dict[str, Any]:
        if bank().session_expired:
            raise HTTPException(status_code=401, detail={"error": "EXPIRED_SESSION"})
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
