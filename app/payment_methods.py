from enum import StrEnum


class PaymentMethod(StrEnum):
    ATM_WITHDRAWAL = "ATM withdrawal"
    CARD_PAYMENT = "Card payment"
    BLIK = "BLIK"
    TRANSFER = "Transfer"
    DIRECT_DEBIT = "Direct debit"
    FEE = "Fee"
    OTHER = "Other"
