from app.bank_profiles import generic
from app.banking.models import Transaction
from app.payment_methods import PaymentMethod


def payment_method(transaction: Transaction) -> PaymentMethod:
    # Mock ASPSP sends no transaction codes; its spending is person-to-person payments to a
    # named creditor. Real banks name the creditor on card payments too, so this stays here.
    method = generic.payment_method(transaction)
    if method is PaymentMethod.OTHER and transaction.creditor and transaction.creditor.name:
        return PaymentMethod.TRANSFER
    return method
