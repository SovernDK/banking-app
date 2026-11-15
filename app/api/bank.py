from typing import Annotated, Self

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.banking.client import BankApiError
from app.banking.errors import BankErrorCode
from app.banking.service import BankingService, InvalidStateError, find_banking_service


class CallbackQuery(BaseModel):
    model_config = ConfigDict(extra="ignore")

    state: str = Field(pattern=r"^\d{1,5}\.[A-Za-z0-9_-]{16,128}$")
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


def callback(
    request: Request,
    service: Annotated[BankingService | None, Depends(find_banking_service)],
) -> RedirectResponse:
    try:
        query = CallbackQuery.model_validate(dict(request.query_params))
    except ValidationError:
        return _back_to_dashboard(BankErrorCode.INVALID_CALLBACK)
    if query.code is None:
        return _back_to_dashboard(BankErrorCode.ACCESS_DENIED)
    if service is None:
        return _back_to_dashboard(BankErrorCode.NOT_CONFIGURED)
    try:
        service.complete(query.code, query.state)
    except InvalidStateError:
        return _back_to_dashboard(BankErrorCode.INVALID_STATE)
    except BankApiError:
        return _back_to_dashboard(BankErrorCode.BANK_UNAVAILABLE)
    return _back_to_dashboard()


def create_router(local_callback_path: str | None = None) -> APIRouter:
    router = APIRouter()
    router.add_api_route("/api/bank/callback", callback, methods=["GET"])
    if local_callback_path:
        router.add_api_route(local_callback_path, callback, methods=["GET"])
    return router
