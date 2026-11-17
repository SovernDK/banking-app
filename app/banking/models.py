import hashlib
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

TransactionStatus = Literal["BOOK", "CNCL", "HOLD", "OTHR", "PDNG", "RJCT", "SCHD"]


class AuthResponse(BaseModel):
    url: HttpUrl


class AccountReference(BaseModel):
    iban: str | None = None

    def iban_hash(self) -> str | None:
        """Compares account numbers without keeping them; banks differ in spacing and case."""
        if not self.iban:
            return None
        normalised = "".join(self.iban.split()).upper()
        return hashlib.sha256(normalised.encode()).hexdigest()


class Account(BaseModel):
    uid: str = Field(min_length=1)
    account_id: AccountReference | None = None
    identification_hash: str | None = Field(
        default=None, min_length=1, description="Names the account the same way in every session."
    )

    @property
    def key(self) -> str:
        return self.identification_hash or self.uid


class SessionAccess(BaseModel):
    valid_until: datetime


class SessionResponse(BaseModel):
    accounts: list[Account]
    access: SessionAccess


class Amount(BaseModel):
    amount: Decimal
    currency: str = Field(pattern=r"^[A-Z]{3}$")


class Party(BaseModel):
    name: str | None = None


class BankTransactionCode(BaseModel):
    """ISO 20022 family (`code`) and sub-family (`sub_code`) of a transaction."""

    description: str | None = None
    code: str | None = None
    sub_code: str | None = None


class Transaction(BaseModel):
    transaction_amount: Amount
    credit_debit_indicator: Literal["DBIT", "CRDT"]
    status: TransactionStatus = "BOOK"
    booking_date: date | None = None
    value_date: date | None = None
    transaction_date: date | None = None
    creditor: Party | None = None
    creditor_account: AccountReference | None = None
    remittance_information: list[str] = []
    bank_transaction_code: BankTransactionCode | None = None


class TransactionsPage(BaseModel):
    transactions: list[Transaction]
    continuation_key: str | None = None
