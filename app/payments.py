from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.payment_methods import PaymentMethod

CurrencyCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]

# ISO 20022 caps an unstructured remittance line at 140 characters.
NAME_MAX_LENGTH = 140


def squash_spaces(text: str) -> str:
    return " ".join(text.split())


def name_key(name: str) -> str:
    """The same for two names that differ only in letter case or spacing."""
    return squash_spaces(name).casefold()


class Payment(BaseModel):
    """One booked payment out of an account: the only bank data Yiji keeps."""

    model_config = ConfigDict(frozen=True)

    name: str | None = Field(default=None, max_length=NAME_MAX_LENGTH)
    payee: str | None = Field(default=None, max_length=NAME_MAX_LENGTH)
    amount: Decimal = Field(gt=0)
    currency: CurrencyCode
    booked_on: date
    payment_method: PaymentMethod = PaymentMethod.OTHER


def counterparty_name(payment: Payment) -> str | None:
    return payment.payee or payment.name


def display_name(payment: Payment) -> str:
    """The counterparty name; a nameless payment, e.g. a cash withdrawal, goes by payment method."""
    return counterparty_name(payment) or payment.payment_method
