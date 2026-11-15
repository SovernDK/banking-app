from app.banking.models import Transaction
from app.payment_methods import PaymentMethod

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
