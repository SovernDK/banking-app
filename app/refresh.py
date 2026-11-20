from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from app.banking.client import BankApiError, BankSessionExpiredError
from app.banking.service import BankingService, NotConnectedError
from app.payments import Payment
from app.rates.book import ExchangeRates
from app.rates.client import RatesUnavailableError


class BankStatus(StrEnum):
    UPDATED = "updated"
    NOT_CONNECTED = "not_connected"
    SESSION_EXPIRED = "session_expired"
    BANK_UNAVAILABLE = "bank_unavailable"


@dataclass(frozen=True)
class Refreshed:
    """What a refresh left behind. The stored payments and rates are there whatever failed, so
    the dashboard can keep showing them. `bank_error` and `rates_error` give the reason a part
    failed; `connection_ends_on` is set only while a bank is connected."""

    bank: BankStatus
    payments: list[Payment]
    rates: ExchangeRates
    connection_ends_on: date | None
    bank_error: str | None = None
    rates_error: str | None = None


def refresh(service: BankingService, *, force: bool = False) -> Refreshed:
    """Stores what the bank booked since the last refresh and the exchange rates those payments
    need. Without `force` the bank is asked only once the refresh window has passed."""
    bank = BankStatus.UPDATED
    bank_error = None
    try:
        service.refresh(force=force)
    except NotConnectedError:
        bank = BankStatus.NOT_CONNECTED
    except BankSessionExpiredError:
        bank = BankStatus.SESSION_EXPIRED
    except BankApiError as error:
        bank = BankStatus.BANK_UNAVAILABLE
        bank_error = str(error)
    payments = service.payments()
    rates_error = None
    try:
        service.refresh_rates(payments)
    except RatesUnavailableError as error:
        rates_error = str(error)
    connected = bank in (BankStatus.UPDATED, BankStatus.BANK_UNAVAILABLE)
    return Refreshed(
        bank=bank,
        payments=payments,
        rates=service.exchange_rates(),
        connection_ends_on=service.connection_ends_on() if connected else None,
        bank_error=bank_error,
        rates_error=rates_error,
    )
