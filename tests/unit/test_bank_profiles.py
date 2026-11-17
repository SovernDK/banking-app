from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from app.bank_profiles import generic, mock_aspsp, pekao, profile_for
from app.banking.models import Transaction
from app.payment_methods import PaymentMethod
from app.payments import Payment, display_name
from tests.fakes.enable_banking import debit

DAY = date(2026, 11, 15)


def _debit(amount: str = "10", **fields: Any) -> Transaction:
    return Transaction.model_validate(debit(amount, DAY, **fields))


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


def test_generic_profile_keeps_only_name_payee_amount_currency_day_and_method() -> None:
    transaction = _debit(
        "-12.50",
        creditor="  Biedronka   Sp. ",
        remittance=["Card  1234 ", "ref 7"],
        family="CCRD",
        sub_family="POSD",
    )

    assert generic.to_payment(transaction) == Payment(
        name="Card 1234",
        payee="Biedronka Sp.",
        amount=Decimal("12.50"),
        currency="EUR",
        booked_on=DAY,
        payment_method=PaymentMethod.CARD_PAYMENT,
    )


@pytest.mark.parametrize(
    "fields",
    [
        pytest.param({"indicator": "CRDT"}, id="income"),
        pytest.param({"status": "PDNG"}, id="pending"),
        pytest.param({"status": "CNCL"}, id="cancelled"),
        pytest.param({"status": "RJCT"}, id="rejected"),
    ],
)
def test_generic_profile_keeps_only_booked_spending(fields: dict[str, Any]) -> None:
    assert generic.to_payment(_debit(**fields)) is None


def test_generic_profile_skips_a_payment_of_nothing() -> None:
    assert generic.to_payment(_debit("0.00")) is None


def test_generic_profile_dates_by_value_date_when_the_bank_gives_no_booking_date() -> None:
    raw = debit("10", DAY)
    del raw["booking_date"]

    assert generic.to_payment(Transaction.model_validate(raw)) is None
    raw["value_date"] = DAY.isoformat()
    payment = generic.to_payment(Transaction.model_validate(raw))
    assert payment is not None and payment.booked_on == DAY


def test_generic_profile_cuts_overlong_names_to_the_iso_line_length() -> None:
    payment = generic.to_payment(_debit(creditor="x" * 300, remittance=[" "]))

    assert payment is not None
    assert payment.payee == "x" * 140
    assert payment.name is None


def test_mock_aspsp_profile_keeps_its_own_payment_method() -> None:
    payment = mock_aspsp.to_payment(_debit(creditor="Aino Korhonen"))

    assert payment is not None and payment.payment_method is PaymentMethod.TRANSFER


@pytest.mark.parametrize(
    ("operation", "expected"),
    [
        ("TRANSAKCJA KARTĄ PŁATNICZĄ", PaymentMethod.CARD_PAYMENT),
        ("PŁATNOŚĆ BLIK", PaymentMethod.BLIK),
        ("PRZELEW BLIK WYCHODZĄCY", PaymentMethod.BLIK),
        ("PRZELEW", PaymentMethod.TRANSFER),
        ("PRZELEW MOBILE", PaymentMethod.TRANSFER),
        ("REALIZACJA PŁATNOŚCI PEOPAY", PaymentMethod.TRANSFER),
        ("PROWIZJE AUT.", PaymentMethod.FEE),
        ("POBRANIE ZALEGŁEJ OPŁATY", PaymentMethod.FEE),
    ],
)
def test_pekao_payment_method_comes_from_its_operation_type_in_the_last_description_line(
    operation: str, expected: PaymentMethod
) -> None:
    transaction = _debit(creditor="Sklep", remittance=["Zakupy listopad", operation])

    assert pekao.payment_method(transaction) is expected


def test_pekao_unknown_operation_type_is_other_and_logged_for_a_new_mapping(
    caplog: pytest.LogCaptureFixture,
) -> None:
    transaction = _debit(remittance=["", "WYPŁATA NOWEGO TYPU"])

    assert pekao.payment_method(transaction) is PaymentMethod.OTHER
    assert "WYPŁATA NOWEGO TYPU" in caplog.text


def test_pekao_payment_without_description_is_other() -> None:
    assert pekao.payment_method(_debit()) is PaymentMethod.OTHER


def test_pekao_blik_reference_is_not_a_payment_name() -> None:
    transaction = _debit(
        creditor="Żabka", remittance=["BLIK REF       12345678901", "PŁATNOŚĆ BLIK"]
    )

    payment = pekao.to_payment(transaction)

    assert payment is not None
    assert (payment.name, payment.payee) == (None, "Żabka")
    assert payment.payment_method is PaymentMethod.BLIK


def test_pekao_card_payment_keeps_payee_and_has_no_name() -> None:
    payment = pekao.to_payment(
        _debit(creditor="Lidl", remittance=["", "TRANSAKCJA KARTĄ PŁATNICZĄ"])
    )

    assert payment is not None
    assert (payment.name, payment.payee) == (None, "Lidl")


def test_pekao_fee_is_named_by_its_description() -> None:
    payment = pekao.to_payment(
        _debit(remittance=["Opłata za obsługę karty debetowej", "PROWIZJE AUT."])
    )

    assert payment is not None
    assert payment.name == "Opłata za obsługę karty debetowej"
    assert payment.payment_method is PaymentMethod.FEE


def test_profile_is_chosen_by_bank_name_and_country() -> None:
    assert profile_for("Mock ASPSP", "FI") is mock_aspsp.to_payment
    assert profile_for("mock aspsp", "FI") is mock_aspsp.to_payment
    assert profile_for("Bank Pekao", "PL") is pekao.to_payment


@pytest.mark.parametrize(("name", "country"), [("Mock ASPSP", "SE"), ("PKO BP", "PL")])
def test_bank_without_its_own_profile_uses_the_generic_one(name: str, country: str) -> None:
    assert profile_for(name, country) is generic.to_payment


@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        ({"creditor": "  Netflix   Inc ", "family": "CCRD", "sub_family": "POSD"}, "Netflix Inc"),
        ({"creditor": "   ", "remittance": ["Spotify Premium"]}, "Spotify Premium"),
        ({"family": "CCRD", "sub_family": "CWDL"}, "ATM withdrawal"),
        ({}, "Other"),
    ],
)
def test_payment_is_named_after_its_payee_else_its_description_else_its_method(
    fields: dict[str, Any], expected: str
) -> None:
    payment = generic.to_payment(_debit(**fields))

    assert payment is not None and display_name(payment) == expected
