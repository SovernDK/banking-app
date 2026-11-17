import logging

from app.bank_profiles import generic
from app.banking.models import Transaction
from app.payment_methods import PaymentMethod
from app.payments import Payment, squash_spaces

logger = logging.getLogger(__name__)

# Pekao sends no ISO transaction codes; its last description line names the operation type.
# Only types seen in real Pekao data are listed, so an unseen one is reported rather than guessed.
_BY_OPERATION = {
    "TRANSAKCJA KARTĄ PŁATNICZĄ": PaymentMethod.CARD_PAYMENT,
    "PŁATNOŚĆ BLIK": PaymentMethod.BLIK,
    "PRZELEW BLIK WYCHODZĄCY": PaymentMethod.BLIK,
    "PRZELEW": PaymentMethod.TRANSFER,
    "PRZELEW MOBILE": PaymentMethod.TRANSFER,
    "REALIZACJA PŁATNOŚCI PEOPAY": PaymentMethod.TRANSFER,
    "PROWIZJE AUT.": PaymentMethod.FEE,
    "POBRANIE ZALEGŁEJ OPŁATY": PaymentMethod.FEE,
}
_BLIK_REFERENCE = "BLIK REF"


def payment_method(transaction: Transaction) -> PaymentMethod:
    if not transaction.remittance_information:
        return PaymentMethod.OTHER
    operation = squash_spaces(transaction.remittance_information[-1]).upper()
    method = _BY_OPERATION.get(operation)
    if method is None:
        # A fixed bank label, never personal data, so it is safe in the server log.
        logger.warning("Unknown Pekao operation type %r counted as Other.", operation)
        return PaymentMethod.OTHER
    return method


def to_payment(transaction: Transaction) -> Payment | None:
    payment = generic.to_payment(transaction, payment_method)
    if payment is not None and payment.name and payment.name.startswith(_BLIK_REFERENCE):
        return payment.model_copy(update={"name": None})
    return payment
