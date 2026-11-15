from collections.abc import Callable

from app.bank_profiles import generic, mock_aspsp
from app.banking.models import Transaction
from app.payment_methods import PaymentMethod

BankProfile = Callable[[Transaction], PaymentMethod]

_PROFILES: dict[tuple[str, str], BankProfile] = {
    ("mock aspsp", "FI"): mock_aspsp.payment_method,
}


def profile_for(aspsp_name: str, aspsp_country: str) -> BankProfile:
    return _PROFILES.get((aspsp_name.casefold(), aspsp_country), generic.payment_method)
