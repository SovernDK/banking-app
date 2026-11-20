import copy
from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Generic, TypeVar
from urllib.parse import urlencode

from app.categories import CategoryBook
from app.counterparties import Counterparties
from app.payments import Payment, counterparty_name, display_name, name_key
from app.rates.book import ExchangeRates, convert_payments
from app.rates.client import EURO
from app.spending import Comparison, DailySpending, Period

Key = TypeVar("Key")

UNCATEGORISED = "uncategorised"
"""Category filter value for spending with no category; real category ids are uuid hex."""


@dataclass(frozen=True)
class SpendingFilter:
    """Narrows spending to one counterparty or one category; with neither it keeps everything."""

    counterparty: str | None = None
    category_id: str | None = None

    def __post_init__(self) -> None:
        if self.counterparty and self.category_id:
            raise ValueError("Filter by a counterparty or a category, not both.")


ALL = SpendingFilter()


@dataclass(frozen=True)
class ViewQuery:
    period: Period = Period.LAST_MONTH
    comparison: Comparison = Comparison.MONTH
    spending_filter: SpendingFilter = ALL


@dataclass(frozen=True)
class Overview:
    """Spending the filter keeps, per day of the period and of its comparison. `subject` names
    the counterparty or category the filter narrows to; `exchanged` and `left_out` describe the
    conversion of the shown days."""

    days: list[DailySpending]
    compared_days: list[DailySpending]
    subject: str | None
    uncategorised: bool
    exchanged: bool
    left_out: int


class SliceKind(StrEnum):
    NAMED = "named"
    OTHER = "other"
    UNCATEGORISED = "uncategorised"


@dataclass(frozen=True)
class Slice:
    """`name` is set for a named slice only; `colour_slot` indexes the category colours."""

    kind: SliceKind
    amount: Decimal
    name: str | None = None
    colour_slot: int | None = None


@dataclass(frozen=True)
class Breakdown:
    counterparties: list[Slice]
    categories: list[Slice]


@dataclass(frozen=True)
class CounterpartyTotal:
    """`amount` is None when no payment to the name has a rate into the display currency."""

    name: str
    amount: Decimal | None
    category_id: str | None
    ai_assigned: bool = False


class SpendingView:
    """Spending in one display currency, answered for any period, comparison and filter.

    Built once per page from the stored payments; the display currency is the requested one
    when it is offered, else the main currency."""

    def __init__(
        self,
        payments: Sequence[Payment],
        rates: ExchangeRates,
        *,
        display_currencies: Sequence[str],
        requested_currency: str | None,
        book: CategoryBook,
        today: date,
        slice_limit: int,
    ) -> None:
        if not payments:
            raise ValueError("A spending view needs at least one payment.")
        self.default_currency = _main_currency(payments, rates)
        others = sorted({payment.currency for payment in payments} - set(display_currencies))
        self.currencies = [*display_currencies, *others]
        self.currency = (
            requested_currency if requested_currency in self.currencies else self.default_currency
        )
        self.stored_payments = list(payments)
        """Every payment as the bank booked it, whether or not it has a rate."""
        conversion = convert_payments(payments, self.currency, rates)
        self.payments = conversion.payments
        """Every payment with a rate, in the display currency."""
        self._names = Counterparties(payments)
        self.counterparties = [share.key for share in _shares(self.payments, self._label)]
        """Every name spending went to, case variants merged, biggest all-time spending first."""
        self._exchanged = conversion.exchanged
        self._left_out = conversion.left_out
        self._book = book
        self._today = today
        self._slice_limit = slice_limit

    @property
    def book(self) -> CategoryBook:
        return self._book

    def with_book(self, book: CategoryBook) -> "SpendingView":
        changed = copy.copy(self)
        changed._book = book
        return changed

    def parse(
        self,
        *,
        period: str | None = None,
        compare: str | None = None,
        counterparty: str | None = None,
        category: str | None = None,
    ) -> ViewQuery:
        """Reads URL values; anything unknown falls back to its default."""
        return ViewQuery(
            Period.parse(period), Comparison.parse(compare), self._filter(counterparty, category)
        )

    def url(self, query: ViewQuery, currency: str | None = None) -> str:
        """The dashboard URL for `query`, in `currency` or the view's own; the main currency is
        left out."""
        currency = currency or self.currency
        values = {
            "period": query.period.value,
            **_filter_values(query.spending_filter),
            "compare": query.comparison.value,
        }
        if currency != self.default_currency:
            values["currency"] = currency
        return f"/?{urlencode(values)}"

    def checked(self, query: ViewQuery) -> ViewQuery:
        """`query` without a filter this view's categories no longer know."""
        spending_filter = query.spending_filter
        return replace(
            query,
            spending_filter=self._filter(spending_filter.counterparty, spending_filter.category_id),
        )

    def overview(self, query: ViewQuery) -> Overview:
        spending_filter = query.spending_filter
        matching = [payment for payment in self.payments if self._matches(payment, spending_filter)]
        compared_end = query.comparison.shift(self._today)

        def shown(candidates: Iterable[Payment]) -> list[Payment]:
            kept = (payment for payment in candidates if self._matches(payment, spending_filter))
            return _booked_within(kept, query.period, [self._today, compared_end])

        return Overview(
            days=_daily(matching, query.period, self._today),
            compared_days=_daily(matching, query.period, compared_end),
            subject=self._subject(spending_filter),
            uncategorised=spending_filter.category_id == UNCATEGORISED,
            exchanged=bool(shown(self._exchanged)),
            left_out=len(shown(self._left_out)),
        )

    def breakdown(self, period: Period) -> Breakdown | None:
        """Where the period's spending went; None when nothing was spent in it."""
        in_period = self._in_period(period)
        if not in_period:
            return None
        counterparties = _shares(in_period, self._label)
        kept, rest = _top_shares(counterparties, self._slice_limit)
        counterparty_slices = [
            Slice(SliceKind.NAMED, share.amount, name=share.key, colour_slot=rank)
            for rank, share in enumerate(kept)
        ]
        if rest:
            counterparty_slices.append(Slice(SliceKind.OTHER, rest))
        return Breakdown(counterparty_slices, self._category_slices(in_period))

    def category_slices(self, period: Period) -> list[Slice]:
        """The categories part of `breakdown`, for when only the categories changed."""
        return self._category_slices(self._in_period(period))

    def counterparty_totals(self) -> list[CounterpartyTotal]:
        """All-time spending per counterparty name, biggest first, with its category. Names
        spent on only in payments without a rate come last, so they can be categorised too."""
        totals: dict[str, Decimal | None] = {
            share.key: share.amount
            for share in _shares(self.payments, self._named_label)
            if share.key is not None
        }
        for payment in self.stored_payments:
            label = self._named_label(payment)
            if label is not None:
                totals.setdefault(label, None)
        return [
            CounterpartyTotal(
                name=name,
                amount=amount,
                category_id=self._category_id(name),
                ai_assigned=self._book.is_ai_assigned(name),
            )
            for name, amount in totals.items()
        ]

    def _category_slices(self, payments: list[Payment]) -> list[Slice]:
        shares = _shares(payments, lambda payment: self._category_id(counterparty_name(payment)))
        categorised = [
            Share(key=category, amount=share.amount)
            for share in shares
            if share.key and (category := self._book.get(share.key))
        ]
        uncategorised = sum((share.amount for share in shares if share.key is None), Decimal(0))
        limit = self._slice_limit - 1 if uncategorised else self._slice_limit
        kept, rest = _top_shares(categorised, limit)
        slices = [
            Slice(
                SliceKind.NAMED,
                share.amount,
                name=share.key.name,
                colour_slot=share.key.colour_slot,
            )
            for share in kept
        ]
        if rest:
            slices.append(Slice(SliceKind.OTHER, rest))
        if uncategorised:
            slices.append(Slice(SliceKind.UNCATEGORISED, uncategorised))
        return slices

    def _in_period(self, period: Period) -> list[Payment]:
        return _booked_within(self.payments, period, [self._today])

    def _label(self, payment: Payment) -> str:
        return self._names.label(display_name(payment))

    def _named_label(self, payment: Payment) -> str | None:
        name = counterparty_name(payment)
        return self._names.label(name) if name else None

    def _category_id(self, counterparty: str | None) -> str | None:
        category = self._book.category_of(counterparty)
        return category.id if category else None

    def _filter(self, counterparty: str | None, category: str | None) -> SpendingFilter:
        """Keeps only a known counterparty or category; anything else is all spending."""
        if counterparty and category:
            return ALL
        if counterparty:
            wanted = name_key(counterparty)
            known = next((name for name in self.counterparties if name_key(name) == wanted), None)
            return SpendingFilter(counterparty=known) if known else ALL
        if category == UNCATEGORISED or (category and self._book.get(category)):
            return SpendingFilter(category_id=category)
        return ALL

    def _matches(self, payment: Payment, spending_filter: SpendingFilter) -> bool:
        if spending_filter.counterparty:
            wanted = name_key(spending_filter.counterparty)
            return name_key(display_name(payment)) == wanted
        if spending_filter.category_id:
            category_id = self._category_id(counterparty_name(payment))
            return (category_id or UNCATEGORISED) == spending_filter.category_id
        return True

    def _subject(self, spending_filter: SpendingFilter) -> str | None:
        if spending_filter.counterparty:
            return spending_filter.counterparty
        category = (
            self._book.get(spending_filter.category_id) if spending_filter.category_id else None
        )
        return category.name if category else None


@dataclass(frozen=True)
class Share(Generic[Key]):
    key: Key
    amount: Decimal


def _filter_values(spending_filter: SpendingFilter) -> dict[str, str]:
    if spending_filter.counterparty:
        return {"counterparty": spending_filter.counterparty}
    if spending_filter.category_id:
        return {"category": spending_filter.category_id}
    return {}


def _main_currency(payments: Iterable[Payment], rates: ExchangeRates) -> str:
    """The currency with the most spending, valued in euros at each payment's rate. Payments
    without a rate are left out of the comparison rather than spoiling it, so one missing rate
    does not change the main currency, and with it the meaning of a saved link. With no rate at
    all the currency with the most payments wins, the bigger amount breaking a tie."""
    values: dict[str, Decimal] = defaultdict(Decimal)
    counts: dict[str, tuple[int, Decimal]] = defaultdict(lambda: (0, Decimal(0)))
    for payment in payments:
        count, amount = counts[payment.currency]
        counts[payment.currency] = (count + 1, amount + payment.amount)
        value = rates.convert(payment.amount, payment.currency, EURO, payment.booked_on)
        if value is not None:
            values[payment.currency] += value
    if values:
        return max(values, key=values.__getitem__)
    return max(counts, key=counts.__getitem__)


def _booked_within(
    payments: Iterable[Payment], period: Period, last_days: Iterable[date]
) -> list[Payment]:
    windows = [(period.first_day(last_day), last_day) for last_day in last_days]
    return [
        payment
        for payment in payments
        if any(first_day <= payment.booked_on <= last_day for first_day, last_day in windows)
    ]


def _daily(payments: Iterable[Payment], period: Period, last_day: date) -> list[DailySpending]:
    first_day = period.first_day(last_day)
    totals: dict[date, Decimal] = defaultdict(Decimal)
    for payment in _booked_within(payments, period, [last_day]):
        totals[payment.booked_on] += payment.amount
    return [
        DailySpending(day=day, amount=totals[day])
        for day in (first_day + timedelta(days=offset) for offset in range(period.days))
    ]


def _shares(payments: Iterable[Payment], key: Callable[[Payment], Key]) -> list[Share[Key]]:
    totals: dict[Key, Decimal] = defaultdict(Decimal)
    for payment in payments:
        totals[key(payment)] += payment.amount
    shares = [Share(key=group, amount=amount) for group, amount in totals.items()]
    return sorted(shares, key=lambda share: share.amount, reverse=True)


def _top_shares(shares: list[Share[Key]], limit: int) -> tuple[list[Share[Key]], Decimal]:
    """At most `limit` slices: the biggest shares, plus the total of the rest when not all fit."""
    if len(shares) <= limit:
        return shares, Decimal(0)
    kept = shares[: limit - 1]
    return kept, sum((share.amount for share in shares[limit - 1 :]), Decimal(0))
