from datetime import date

from app.payment_methods import PaymentMethod
from app.payments import Payment


def payment(
    amount: str,
    booked_on: date,
    *,
    currency: str = "EUR",
    payee: str | None = None,
    name: str | None = None,
    method: PaymentMethod = PaymentMethod.OTHER,
) -> Payment:
    return Payment.model_validate(
        {
            "amount": amount,
            "currency": currency,
            "booked_on": booked_on,
            "payee": payee,
            "name": name,
            "payment_method": method,
        }
    )
