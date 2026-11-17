from collections.abc import Callable

from app.banking.models import Transaction
from app.payment_methods import PaymentMethod
from app.payments import NAME_MAX_LENGTH, Payment, squash_spaces

_BY_SUB_FAMILY = {
    "CWDL": PaymentMethod.ATM_WITHDRAWAL,
    "CHRG": PaymentMethod.FEE,
    "FEES": PaymentMethod.FEE,
    "COMM": PaymentMethod.FEE,
}
_BY_FAMILY = {
    "CCRD": PaymentMethod.CARD_PAYMENT,
    "MCRD": PaymentMethod.CARD_PAYMENT,
    "ICDT": PaymentMethod.TRANSFER,
    "RCDT": PaymentMethod.TRANSFER,
    "IDDT": PaymentMethod.DIRECT_DEBIT,
    "RDDT": PaymentMethod.DIRECT_DEBIT,
}


def payment_method(transaction: Transaction) -> PaymentMethod:
    """Reads the ISO 20022 bank transaction code, which is all a bank-neutral profile can trust."""
    code = transaction.bank_transaction_code
    if code is None:
        return PaymentMethod.OTHER
    return _BY_SUB_FAMILY.get(code.sub_code or "") or _BY_FAMILY.get(
        code.code or "", PaymentMethod.OTHER
    )


def _name(text: str | None) -> str | None:
    cleaned = squash_spaces(text or "")[:NAME_MAX_LENGTH]
    return cleaned or None


def to_payment(
    transaction: Transaction,
    method: Callable[[Transaction], PaymentMethod] = payment_method,
) -> Payment | None:
    """Keeps booked debits only, and of them only what the charts need."""
    booked_on = transaction.booking_date or transaction.value_date
    # Banks differ on whether debit amounts are signed; the indicator carries the direction.
    amount = abs(transaction.transaction_amount.amount)
    if (
        transaction.status != "BOOK"
        or transaction.credit_debit_indicator != "DBIT"
        or booked_on is None
        or not amount
    ):
        return None
    return Payment(
        name=_name(next(iter(transaction.remittance_information), None)),
        payee=_name(transaction.creditor.name if transaction.creditor else None),
        amount=amount,
        currency=transaction.transaction_amount.currency,
        booked_on=booked_on,
        payment_method=method(transaction),
    )
