from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

TransactionStatus = Literal["BOOK", "CNCL", "HOLD", "OTHR", "PDNG", "RJCT", "SCHD"]


class AuthResponse(BaseModel):
    url: HttpUrl
    authorization_id: str


class Account(BaseModel):
    uid: str = Field(min_length=1)
    currency: str | None = None


class SessionAccess(BaseModel):
    valid_until: datetime


class SessionResponse(BaseModel):
    session_id: str = Field(min_length=1)
    accounts: list[Account]
    access: SessionAccess


class Amount(BaseModel):
    amount: Decimal
    currency: str = Field(pattern=r"^[A-Z]{3}$")


class Transaction(BaseModel):
    transaction_amount: Amount
    credit_debit_indicator: Literal["DBIT", "CRDT"]
    status: TransactionStatus = "BOOK"
    booking_date: date | None = None
    value_date: date | None = None
    transaction_date: date | None = None

    @property
    def spent_on(self) -> date | None:
        return self.booking_date or self.value_date or self.transaction_date


class TransactionsPage(BaseModel):
    transactions: list[Transaction]
    continuation_key: str | None = None
