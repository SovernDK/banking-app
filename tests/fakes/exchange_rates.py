"""In-memory stand-in for the Frankfurter exchange rate API, used by unit tests (via TestClient)
and e2e tests (served by uvicorn). Only the date-range endpoint Yiji calls is implemented."""

from datetime import date
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict


class FakeRatesConfig(BaseModel):
    rates: dict[str, dict[str, str]] = {}
    """Units per euro, by ISO day and currency; days left out were not published."""
    failure_status: int | None = None


class FakeRatesState(FakeRatesConfig):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    requests: list[Request] = []


def create_fake_exchange_rates() -> FastAPI:
    fake = FastAPI()
    fake.state.rates = FakeRatesState()

    def state() -> FakeRatesState:
        return fake.state.rates

    @fake.get("/{days}", response_model=None)
    def daily_rates(days: str, request: Request, base: str, symbols: str) -> Response | dict:
        state().requests.append(request)
        failure_status = state().failure_status
        if failure_status is not None:
            return JSONResponse({"message": "fake failure"}, status_code=failure_status)
        first, _, last = days.partition("..")
        published = sorted(day for day in state().rates if day <= last)
        in_range = [day for day in published if day >= first]
        # Like Frankfurter, a range with no publication day answers the latest one before it.
        shown = in_range or published[-1:]
        wanted = symbols.split(",")
        rates: dict[str, Any] = {
            day: {
                currency: float(rate)
                for currency, rate in state().rates[day].items()
                if currency in wanted
            }
            for day in shown
        }
        return {"amount": 1.0, "base": base, "rates": rates}

    @fake.post("/_fake/configure")
    def configure(config: FakeRatesConfig) -> None:
        fake.state.rates = FakeRatesState(**config.model_dump())

    return fake


def daily(first_day: date, last_day: date, **per_euro: str) -> dict[str, dict[str, str]]:
    """The same rates published on every weekday from `first_day` to `last_day`."""
    return {
        day.isoformat(): dict(per_euro)
        for day in (
            date.fromordinal(ordinal)
            for ordinal in range(first_day.toordinal(), last_day.toordinal() + 1)
        )
        if day.weekday() < 5
    }
