from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

TransactionStatus = Literal["BOOK", "CNCL", "HOLD", "OTHR", "PDNG", "RJCT", "SCHD"]


class AuthResponse(BaseModel):
    url: HttpUrl


class Account(BaseModel):
    uid: str = Field(min_length=1)


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
    remittance_information: list[str] = []
    bank_transaction_code: BankTransactionCode | None = None

    @property
    def spent_on(self) -> date | None:
        return self.booking_date or self.value_date or self.transaction_date


class TransactionsPage(BaseModel):
    transactions: list[Transaction]
    continuation_key: str | None = None
