from collections.abc import Callable
from typing import Self

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, ValidationError, model_validator

from app.banking.client import BankApiError
from app.banking.errors import BankErrorCode
from app.banking.service import InvalidStateError
from app.banking.state import STATE_PATTERN

# Also hard-coded in site/callback.html, the hosted page that relays to it.
CALLBACK_PATH = "/api/bank/callback"


class CallbackQuery(BaseModel):
    state: str = Field(pattern=STATE_PATTERN)
    code: str | None = Field(default=None, min_length=1, max_length=2048)
    error: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _code_or_error(self) -> Self:
        if (self.code is None) == (self.error is None):
            raise ValueError("expected exactly one of code or error")
        return self


def _back_to_dashboard(error: BankErrorCode | None = None) -> RedirectResponse:
    location = "/" if error is None else f"/?bank_error={error}"
    return RedirectResponse(location, status_code=303)


Complete = Callable[[str, str], None]
"""Finishes a bank connection from the code and state the bank sent back."""


def _callback(request: Request, complete: Complete | None) -> RedirectResponse:
    try:
        query = CallbackQuery.model_validate(dict(request.query_params))
    except ValidationError:
        return _back_to_dashboard(BankErrorCode.INVALID_CALLBACK)
    if query.code is None:
        return _back_to_dashboard(BankErrorCode.ACCESS_DENIED)
    if complete is None:
        return _back_to_dashboard(BankErrorCode.NOT_CONFIGURED)
    try:
        complete(query.code, query.state)
    except InvalidStateError:
        return _back_to_dashboard(BankErrorCode.INVALID_STATE)
    except BankApiError:
        return _back_to_dashboard(BankErrorCode.BANK_UNAVAILABLE)
    return _back_to_dashboard()


def create_router(complete: Complete | None, local_callback_path: str | None = None) -> APIRouter:
    """Without `complete` (no bank credentials) the callback says Yiji is not configured."""
    router = APIRouter()

    def callback(request: Request) -> RedirectResponse:
        return _callback(request, complete)

    for path in {CALLBACK_PATH, local_callback_path} - {None}:
        router.add_api_route(path, callback, methods=["GET"])
    return router
