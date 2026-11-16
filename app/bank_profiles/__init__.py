from collections.abc import Callable

from app.bank_profiles import generic, mock_aspsp
from app.banking.models import Transaction
from app.categories import counterparty_name
from app.payment_methods import PaymentMethod

BankProfile = Callable[[Transaction], PaymentMethod]

_PROFILES: dict[tuple[str, str], BankProfile] = {
    ("mock aspsp", "FI"): mock_aspsp.payment_method,
}


def profile_for(aspsp_name: str, aspsp_country: str) -> BankProfile:
    return _PROFILES.get((aspsp_name.casefold(), aspsp_country), generic.payment_method)


def transaction_name(transaction: Transaction, profile: BankProfile) -> str:
    """The counterparty name; a nameless payment, e.g. a cash withdrawal, goes by payment method."""
    return counterparty_name(transaction) or profile(transaction)
