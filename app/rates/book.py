import bisect
from collections import defaultdict
from collections.abc import Collection, Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from app.database import connect
from app.payments import Payment
from app.rates.client import EURO, ExchangeRateClient

ONE_DAY = timedelta(days=1)


class ExchangeRates:
    """Looks up the rate in force on a day: the latest published on or before it, as long as
    that is no more than `lookback` earlier."""

    def __init__(
        self, per_euro: dict[str, list[tuple[date, Decimal]]], lookback: timedelta
    ) -> None:
        self._per_euro = per_euro
        self._days = {currency: [day for day, _ in rates] for currency, rates in per_euro.items()}
        self._lookback = lookback

    def _rate(self, currency: str, day: date) -> Decimal | None:
        if currency == EURO:
            return Decimal(1)
        index = bisect.bisect_right(self._days.get(currency, []), day) - 1
        if index < 0:
            return None
        published_on, rate = self._per_euro[currency][index]
        return rate if day - published_on <= self._lookback else None

    def convert(self, amount: Decimal, source: str, target: str, day: date) -> Decimal | None:
        """`amount` in `target` at the day's rates; None when a rate for that day is missing."""
        if source == target:
            return amount
        source_rate, target_rate = self._rate(source, day), self._rate(target, day)
        if source_rate is None or target_rate is None:
            return None
        return amount / source_rate * target_rate


@dataclass(frozen=True)
class Conversion:
    """`payments` holds every payment with a rate, in one currency; `exchanged` those of them
    booked in another currency; `left_out` the payments, as booked, that had no rate."""

    payments: list[Payment]
    exchanged: list[Payment]
    left_out: list[Payment]


def convert_payments(
    payments: Iterable[Payment], currency: str, rates: ExchangeRates
) -> Conversion:
    """The payments in `currency`, each at its booking day's rate."""
    conversion = Conversion(payments=[], exchanged=[], left_out=[])
    for payment in payments:
        amount = rates.convert(payment.amount, payment.currency, currency, payment.booked_on)
        if amount is None:
            conversion.left_out.append(payment)
            continue
        shown = payment.model_copy(update={"amount": amount, "currency": currency})
        conversion.payments.append(shown)
        if payment.currency != currency:
            conversion.exchanged.append(shown)
    return conversion


@dataclass(frozen=True)
class _Coverage:
    """The days a currency's rates were fetched for, and when that was last checked."""

    first_day: date
    last_day: date
    checked_at: datetime

    def widened(self, first_day: date, last_day: date, now: datetime) -> "_Coverage":
        return _Coverage(min(self.first_day, first_day), max(self.last_day, last_day), now)


class RateBook:
    """Daily rates kept locally, so each day is fetched once."""

    def __init__(self, path: Path, client: ExchangeRateClient, lookback_days: int) -> None:
        self._path = path
        self._client = client
        self._lookback = timedelta(days=lookback_days)

    def refresh(
        self,
        currencies: Collection[str],
        first_day: date,
        today: date,
        now: datetime,
        max_age: timedelta,
    ) -> None:
        """Fetches what is missing for `currencies` from `first_day` (less the lookback) to today.

        Today's rate may not be published yet, so today is asked for again once `max_age` has
        passed; earlier days are final once fetched."""
        start = first_day - self._lookback
        coverage = self._coverage()
        missing: dict[str, tuple[date, date]] = {}
        for currency in sorted(set(currencies) - {EURO}):
            covered = coverage.get(currency)
            if covered is None:
                missing[currency] = (start, today)
                continue
            gaps: list[tuple[date, date]] = []
            if start < covered.first_day:
                gaps.append((start, covered.first_day - ONE_DAY))
            if covered.last_day < today - ONE_DAY or (
                covered.last_day < today and now - covered.checked_at >= max_age
            ):
                gaps.append((covered.last_day + ONE_DAY, today))
            if gaps:
                missing[currency] = (min(gap[0] for gap in gaps), max(gap[1] for gap in gaps))
        if not missing:
            return
        fetch_from = min(gap[0] for gap in missing.values())
        fetch_to = max(gap[1] for gap in missing.values())
        rates = self._client.fetch(fetch_from, fetch_to, missing.keys())
        final_day = min(fetch_to, today - ONE_DAY)
        fetched = _Coverage(fetch_from, final_day, now)
        with connect(self._path) as connection:
            connection.executemany(
                "INSERT OR REPLACE INTO exchange_rates (day, currency, per_euro) VALUES (?, ?, ?)",
                [
                    (day.isoformat(), currency, str(rate))
                    for day, day_rates in rates.items()
                    for currency, rate in day_rates.items()
                ],
            )
            connection.executemany(
                "INSERT OR REPLACE INTO exchange_rate_coverage"
                " (currency, first_day, last_day, checked_at) VALUES (?, ?, ?, ?)",
                [
                    (
                        currency,
                        widened.first_day.isoformat(),
                        widened.last_day.isoformat(),
                        now.isoformat(),
                    )
                    for currency in missing
                    for widened in [
                        coverage.get(currency, fetched).widened(fetch_from, final_day, now)
                    ]
                ],
            )

    def rates(self) -> ExchangeRates:
        per_euro: dict[str, list[tuple[date, Decimal]]] = defaultdict(list)
        with connect(self._path) as connection:
            rows = connection.execute(
                "SELECT day, currency, per_euro FROM exchange_rates ORDER BY day"
            ).fetchall()
        for row in rows:
            per_euro[row["currency"]].append(
                (date.fromisoformat(row["day"]), Decimal(row["per_euro"]))
            )
        return ExchangeRates(dict(per_euro), self._lookback)

    def _coverage(self) -> dict[str, _Coverage]:
        with connect(self._path) as connection:
            rows = connection.execute(
                "SELECT currency, first_day, last_day, checked_at FROM exchange_rate_coverage"
            ).fetchall()
        return {
            row["currency"]: _Coverage(
                first_day=date.fromisoformat(row["first_day"]),
                last_day=date.fromisoformat(row["last_day"]),
                checked_at=datetime.fromisoformat(row["checked_at"]),
            )
            for row in rows
        }
