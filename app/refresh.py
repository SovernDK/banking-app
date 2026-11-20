from collections.abc import Callable, Collection
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from app.banking.client import BankApiError, BankSessionExpiredError
from app.banking.history import HistoryStore
from app.banking.service import BankingService, NotConnectedError, local_now
from app.payments import Payment
from app.rates.book import ExchangeRates, RateBook
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
    failed."""

    bank: BankStatus
    payments: list[Payment]
    rates: ExchangeRates
    bank_error: str | None = None
    rates_error: str | None = None

    @property
    def needs_connection(self) -> bool:
        return self.bank in (BankStatus.NOT_CONNECTED, BankStatus.SESSION_EXPIRED)


class Refresher:
    """Brings the spending history and the exchange rates it needs up to date."""

    def __init__(
        self,
        bank: BankingService,
        history: HistoryStore,
        rate_book: RateBook,
        *,
        display_currencies: Collection[str],
        max_age: timedelta,
        now: Callable[[], datetime] = local_now,
    ) -> None:
        """`max_age` is how long today's exchange rates count as current."""
        self._bank = bank
        self._history = history
        self._rate_book = rate_book
        self._display_currencies = display_currencies
        self._max_age = max_age
        self._now = now

    def refresh(self, *, force: bool = False) -> Refreshed:
        """Stores what the bank booked since the last refresh and the exchange rates those
        payments need. Without `force` the bank is asked only once its refresh window has
        passed."""
        bank = BankStatus.UPDATED
        bank_error = None
        try:
            self._bank.refresh(force=force)
        except NotConnectedError:
            bank = BankStatus.NOT_CONNECTED
        except BankSessionExpiredError:
            bank = BankStatus.SESSION_EXPIRED
        except BankApiError as error:
            bank = BankStatus.BANK_UNAVAILABLE
            bank_error = str(error)
        payments = self._history.payments()
        rates_error = None
        try:
            self._refresh_rates(payments)
        except RatesUnavailableError as error:
            rates_error = str(error)
        return Refreshed(
            bank=bank,
            payments=payments,
            rates=self._rate_book.rates(),
            bank_error=bank_error,
            rates_error=rates_error,
        )

    def _refresh_rates(self, payments: list[Payment]) -> None:
        """Fetches the rates the payments and the display currencies still lack."""
        if not payments:
            return
        now = self._now()
        self._rate_book.refresh(
            {payment.currency for payment in payments} | set(self._display_currencies),
            min(payment.booked_on for payment in payments),
            now.date(),
            now,
            self._max_age,
        )
