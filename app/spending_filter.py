from collections.abc import Sequence
from dataclasses import dataclass

from app.bank_profiles import BankProfile, transaction_name
from app.banking.models import Transaction
from app.categories import CategoryBook, counterparty_name
from app.spending import all_time_spending_by, merge_spellings

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

    @classmethod
    def parse(
        cls,
        counterparty: str | None,
        category: str | None,
        counterparties: Sequence[str],
        book: CategoryBook,
    ) -> "SpendingFilter":
        """Reads URL values, keeping only a known counterparty or category; anything else is all."""
        if counterparty and category:
            return ALL
        if counterparty:
            wanted = counterparty.casefold()
            known = next((name for name in counterparties if name.casefold() == wanted), None)
            return cls(counterparty=known) if known else ALL
        if category == UNCATEGORISED or (category and book.get(category)):
            return cls(category_id=category)
        return ALL

    def matches(self, transaction: Transaction, profile: BankProfile, book: CategoryBook) -> bool:
        if self.counterparty:
            name = transaction_name(transaction, profile)
            return name.casefold() == self.counterparty.casefold()
        if self.category_id:
            category = book.category_of(counterparty_name(transaction))
            return (category.id if category else UNCATEGORISED) == self.category_id
        return True

    def subject(self, book: CategoryBook) -> str | None:
        if self.counterparty:
            return self.counterparty
        if self.category_id == UNCATEGORISED:
            return "uncategorised"
        category = book.get(self.category_id) if self.category_id else None
        return category.name if category else None

    def query(self) -> dict[str, str]:
        if self.counterparty:
            return {"counterparty": self.counterparty}
        if self.category_id:
            return {"category": self.category_id}
        return {}


ALL = SpendingFilter()


def counterparty_names(
    transactions: list[Transaction], currency: str, profile: BankProfile
) -> list[str]:
    """Every name spending went to, case variants merged, biggest all-time spending first."""
    shares = all_time_spending_by(
        transactions, currency, lambda transaction: transaction_name(transaction, profile)
    )
    return [share.key for share in merge_spellings(shares)]
