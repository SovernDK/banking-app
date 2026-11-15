from datetime import date
from pathlib import Path

import pytest

from app.banking.models import Transaction
from app.categories import (
    CATEGORIES_FILENAME,
    CategoryBook,
    CategoryStore,
    DuplicateCategoryError,
    InvalidCategoryNameError,
    counterparty_name,
)
from tests.fakes.enable_banking import debit

DAY = date(2026, 11, 15)


def _debit(creditor: str | None = None, remittance: list[str] | None = None) -> Transaction:
    return Transaction.model_validate(debit("10", DAY, creditor=creditor, remittance=remittance))


@pytest.mark.parametrize(
    ("creditor", "remittance", "expected"),
    [
        ("Biedronka", ["Card 1234"], "Biedronka"),
        (None, ["Rent  November ", "ref 7"], "Rent November"),
        ("   ", ["Rent"], "Rent"),
        (None, [], None),
    ],
)
def test_counterparty_is_creditor_name_else_first_description_line(
    creditor: str | None, remittance: list[str], expected: str | None
) -> None:
    assert counterparty_name(_debit(creditor, remittance)) == expected


def test_rule_applies_to_names_differing_only_in_case_and_spacing() -> None:
    book = CategoryBook()
    groceries = book.create("Groceries")

    book.assign("Biedronka", groceries.id)

    assert book.category_of(" BIEDRONKA ") == groceries
    assert book.category_of("Biedronka 123") is None
    assert book.category_of(None) is None


def test_assigning_none_makes_the_name_uncategorised() -> None:
    book = CategoryBook()
    groceries = book.create("Groceries")
    book.assign("Biedronka", groceries.id)

    book.assign("Biedronka", None)

    assert book.category_of("Biedronka") is None


@pytest.mark.parametrize("name", ["", "   ", "x" * 41])
def test_rejects_category_name_that_is_blank_or_too_long(name: str) -> None:
    with pytest.raises(InvalidCategoryNameError):
        CategoryBook().create(name)


def test_rejects_category_name_already_taken_ignoring_case() -> None:
    book = CategoryBook()
    book.create("Groceries")

    with pytest.raises(DuplicateCategoryError):
        book.create(" groceries ")


def test_rename_keeps_rules_and_colour_but_not_a_taken_name() -> None:
    book = CategoryBook()
    groceries = book.create("Groceries")
    book.create("Rent")
    book.assign("Biedronka", groceries.id)
    colour = groceries.colour_slot

    book.rename(groceries.id, "Food")

    assert book.category_of("Biedronka") == groceries
    assert (groceries.name, groceries.colour_slot) == ("Food", colour)
    with pytest.raises(DuplicateCategoryError):
        book.rename(groceries.id, "rent")
    book.rename(groceries.id, "FOOD")
    assert groceries.name == "FOOD"


def test_deleting_a_category_makes_its_names_uncategorised() -> None:
    book = CategoryBook()
    groceries = book.create("Groceries")
    rent = book.create("Rent")
    book.assign("Biedronka", groceries.id)
    book.assign("Lidl", groceries.id)
    book.assign("Landlord", rent.id)
    assert book.usage(groceries.id) == 2

    book.delete(groceries.id)

    assert book.get(groceries.id) is None
    assert book.category_of("Biedronka") is None
    assert book.category_of("Landlord") == rent


def test_unknown_category_cannot_be_assigned_or_deleted() -> None:
    book = CategoryBook()

    with pytest.raises(KeyError):
        book.assign("Biedronka", "missing")
    with pytest.raises(KeyError):
        book.delete("missing")


def test_categories_in_use_get_distinct_colours_and_unused_ones_hold_none() -> None:
    book = CategoryBook()
    groceries, *_, housing = [
        book.create(name) for name in ["Groceries", "Eating out", "Transport", "Housing"]
    ]
    rent = book.create("Rent")

    book.assign("Landlord", rent.id)
    book.assign("Plumber", housing.id)

    assert (rent.colour_slot, housing.colour_slot) == (0, 1)
    assert groceries.colour_slot is None


def test_colour_freed_by_a_deleted_category_is_reused() -> None:
    book = CategoryBook()
    rent = book.create("Rent")
    food = book.create("Food")
    book.assign("Landlord", rent.id)
    book.delete(rent.id)

    book.assign("Lidl", food.id)

    assert food.colour_slot == 0


def test_store_seeds_starter_categories_once_and_keeps_changes(tmp_path: Path) -> None:
    path = tmp_path / CATEGORIES_FILENAME
    store = CategoryStore(path, ["Groceries", "Rent"])
    book = store.load()
    assert [category.name for category in book.categories] == ["Groceries", "Rent"]

    book.assign("Biedronka", book.categories[0].id)
    book.delete(book.categories[1].id)
    store.save(book)

    reloaded = CategoryStore(path, ["Groceries", "Rent", "Health"]).load()
    assert [category.name for category in reloaded.categories] == ["Groceries"]
    assert reloaded.category_of("biedronka") == reloaded.categories[0]


def test_unreadable_category_file_starts_empty(tmp_path: Path) -> None:
    path = tmp_path / CATEGORIES_FILENAME
    path.write_text("{not json")

    assert CategoryStore(path, ["Groceries"]).load() == CategoryBook()
