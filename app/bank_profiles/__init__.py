from collections.abc import Callable

from app.bank_profiles import generic, mock_aspsp, pekao
from app.banking.models import Transaction
from app.payments import Payment

BankProfile = Callable[[Transaction], Payment | None]
"""Reads one bank's transaction into the payment Yiji keeps; None for anything not kept."""

_PROFILES: dict[tuple[str, str], BankProfile] = {
    ("mock aspsp", "FI"): mock_aspsp.to_payment,
    ("bank pekao", "PL"): pekao.to_payment,
}


def profile_for(aspsp_name: str, aspsp_country: str) -> BankProfile:
    return _PROFILES.get((aspsp_name.casefold(), aspsp_country), generic.to_payment)
