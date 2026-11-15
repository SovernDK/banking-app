from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, TypeVar

import httpx2
import jwt
from pydantic import BaseModel, ValidationError

from app.banking.models import AuthResponse, SessionResponse, Transaction, TransactionsPage

JWT_LIFETIME = timedelta(hours=1)

ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


class BankApiError(Exception):
    pass


class BankSessionExpiredError(BankApiError):
    pass


class EnableBankingClient:
    def __init__(self, http: httpx2.Client, app_id: str, key_path: Path) -> None:
        self._http = http
        self._app_id = app_id
        self._private_key = key_path.read_text()

    def start_authorization(
        self,
        *,
        aspsp_name: str,
        aspsp_country: str,
        redirect_url: str,
        state: str,
        valid_until: datetime,
    ) -> str:
        body = {
            "access": {"valid_until": valid_until.isoformat()},
            "aspsp": {"name": aspsp_name, "country": aspsp_country},
            "state": state,
            "redirect_url": redirect_url,
            "psu_type": "personal",
        }
        return str(self._request("POST", "/auth", AuthResponse, json=body).url)

    def create_session(self, code: str) -> SessionResponse:
        return self._request("POST", "/sessions", SessionResponse, json={"code": code})

    def fetch_transactions(self, account_uid: str, date_from: date) -> list[Transaction]:
        transactions: list[Transaction] = []
        params: dict[str, str] = {"date_from": date_from.isoformat()}
        while True:
            page = self._request(
                "GET", f"/accounts/{account_uid}/transactions", TransactionsPage, params=params
            )
            transactions.extend(page.transactions)
            if not page.continuation_key:
                return transactions
            params["continuation_key"] = page.continuation_key

    def _token(self) -> str:
        issued_at = datetime.now(UTC)
        claims = {
            "iss": "enablebanking.com",
            "aud": "api.enablebanking.com",
            "iat": int(issued_at.timestamp()),
            "exp": int((issued_at + JWT_LIFETIME).timestamp()),
        }
        return jwt.encode(
            claims, self._private_key, algorithm="RS256", headers={"kid": self._app_id}
        )

    def _request(
        self, method: str, path: str, response_model: type[ResponseModel], **kwargs: Any
    ) -> ResponseModel:
        headers = {"Authorization": f"Bearer {self._token()}"}
        try:
            response = self._http.request(method, path, headers=headers, **kwargs)
        except httpx2.HTTPError as error:
            raise BankApiError("The bank service could not be reached.") from error
        if response.status_code in {401, 403} and path.startswith("/accounts/"):
            raise BankSessionExpiredError("The bank connection has expired.")
        if response.is_error:
            raise BankApiError(f"The bank service returned an error ({response.status_code}).")
        try:
            return response_model.model_validate_json(response.content)
        except ValidationError as error:
            raise BankApiError("The bank service returned unexpected data.") from error
