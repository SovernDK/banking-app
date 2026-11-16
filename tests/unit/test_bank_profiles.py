from datetime import date
from typing import Any

import pytest

from app.bank_profiles import generic, mock_aspsp, profile_for, transaction_name
from app.banking.models import Transaction
from app.payment_methods import PaymentMethod
from tests.fakes.enable_banking import debit

DAY = date(2026, 11, 15)


def _debit(**fields: Any) -> Transaction:
    return Transaction.model_validate(debit("10", DAY, **fields))


@pytest.mark.parametrize(
    ("family", "sub_family", "expected"),
    [
        ("CCRD", "CWDL", PaymentMethod.ATM_WITHDRAWAL),
        ("CNTR", "CWDL", PaymentMethod.ATM_WITHDRAWAL),
        ("CCRD", "POSD", PaymentMethod.CARD_PAYMENT),
        ("MCRD", None, PaymentMethod.CARD_PAYMENT),
        ("CCRD", "CHRG", PaymentMethod.FEE),
        ("ICDT", "STDO", PaymentMethod.TRANSFER),
        ("RDDT", None, PaymentMethod.DIRECT_DEBIT),
        ("XTND", "NTAV", PaymentMethod.OTHER),
    ],
)
def test_generic_profile_reads_iso_bank_transaction_codes(
    family: str, sub_family: str | None, expected: PaymentMethod
) -> None:
    transaction = Transaction.model_validate(debit("10", DAY, family=family, sub_family=sub_family))

    assert generic.payment_method(transaction) is expected


def test_generic_profile_answers_other_without_a_code_even_when_creditor_is_named() -> None:
    assert generic.payment_method(_debit(creditor="Biedronka")) is PaymentMethod.OTHER


def test_mock_aspsp_payment_to_a_named_creditor_is_a_transfer() -> None:
    transaction = _debit(creditor="Aino Korhonen")

    assert mock_aspsp.payment_method(transaction) is PaymentMethod.TRANSFER


def test_mock_aspsp_still_trusts_a_bank_transaction_code() -> None:
    transaction = _debit(creditor="Aino Korhonen", family="CCRD", sub_family="CWDL")

    assert mock_aspsp.payment_method(transaction) is PaymentMethod.ATM_WITHDRAWAL


def test_mock_aspsp_payment_without_creditor_or_code_is_other() -> None:
    assert mock_aspsp.payment_method(_debit()) is PaymentMethod.OTHER


def test_profile_is_chosen_by_bank_name_and_country() -> None:
    assert profile_for("Mock ASPSP", "FI") is mock_aspsp.payment_method
    assert profile_for("mock aspsp", "FI") is mock_aspsp.payment_method


@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        ({"creditor": "  Netflix   Inc ", "family": "CCRD", "sub_family": "POSD"}, "Netflix Inc"),
        ({"remittance": ["Spotify Premium"]}, "Spotify Premium"),
        ({"family": "CCRD", "sub_family": "CWDL"}, "ATM withdrawal"),
        ({}, "Other"),
    ],
)
def test_transaction_is_named_after_its_counterparty_else_its_payment_method(
    fields: dict[str, Any], expected: str
) -> None:
    assert transaction_name(_debit(**fields), generic.payment_method) == expected


@pytest.mark.parametrize(("name", "country"), [("Mock ASPSP", "SE"), ("PKO BP", "PL")])
def test_bank_without_its_own_profile_uses_the_generic_one(name: str, country: str) -> None:
    assert profile_for(name, country) is generic.payment_method
