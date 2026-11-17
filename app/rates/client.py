from collections.abc import Collection
from datetime import date
from decimal import Decimal
from typing import Annotated

import httpx2
from pydantic import BaseModel, Field, ValidationError

from app.payments import CurrencyCode

EURO = "EUR"

DailyRates = dict[date, dict[CurrencyCode, Annotated[Decimal, Field(gt=0)]]]


class RatesUnavailableError(Exception):
    pass


class _RatesRange(BaseModel):
    rates: DailyRates


class ExchangeRateClient:
    """Euro reference rates published daily by the ECB, served by the Frankfurter API."""

    def __init__(self, http: httpx2.Client) -> None:
        self._http = http

    def fetch(self, first_day: date, last_day: date, currencies: Collection[str]) -> DailyRates:
        """Units of each currency per euro, for every publication day in the range; a range
        with no publication day in it answers the latest one before it."""
        try:
            response = self._http.get(
                f"/{first_day.isoformat()}..{last_day.isoformat()}",
                params={"base": EURO, "symbols": ",".join(sorted(currencies))},
            )
            response.raise_for_status()
        except httpx2.HTTPError as error:
            raise RatesUnavailableError("Exchange rates could not be fetched.") from error
        try:
            return _RatesRange.model_validate_json(response.content).rates
        except ValidationError as error:
            raise RatesUnavailableError("The exchange rate service returned bad data.") from error
