from pathlib import Path

import pytest

from app.categories import (
    CATEGORIES_FILENAME,
    CategoryBook,
    CategoryStore,
    DuplicateCategoryError,
    InvalidCategoryNameError,
)


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


def test_ai_choice_fills_only_names_the_user_left_uncategorised() -> None:
    book = CategoryBook()
    groceries = book.create("Groceries")
    eating_out = book.create("Eating out")
    book.assign("Biedronka", groceries.id)

    assert not book.assign_suggested("BIEDRONKA", eating_out.id)
    assert book.assign_suggested("Żabka", groceries.id)

    assert book.category_of("Biedronka") == groceries
    assert not book.is_ai_assigned("Biedronka")
    assert book.category_of("żabka") == groceries
    assert book.is_ai_assigned("żabka")
    assert groceries.colour_slot is not None


def test_user_correcting_an_ai_choice_makes_it_their_own() -> None:
    book = CategoryBook()
    groceries = book.create("Groceries")
    eating_out = book.create("Eating out")
    book.assign_suggested("Żabka", groceries.id)

    book.assign("Żabka", eating_out.id)

    assert book.category_of("Żabka") == eating_out
    assert not book.is_ai_assigned("Żabka")


def test_deleting_a_category_forgets_its_ai_choices() -> None:
    book = CategoryBook()
    groceries = book.create("Groceries")
    book.assign_suggested("Żabka", groceries.id)

    book.delete(groceries.id)

    assert not book.is_ai_assigned("Żabka")


def test_category_file_from_before_ai_choices_still_loads(tmp_path: Path) -> None:
    path = tmp_path / CATEGORIES_FILENAME
    path.write_text(
        '{"categories": [{"id": "g", "name": "Groceries", "colour_slot": 0}],'
        ' "rules": {"biedronka": "g"}}'
    )

    book = CategoryStore(path, []).load()

    assert book.category_of("Biedronka") == book.get("g")
    assert not book.is_ai_assigned("Biedronka")


def test_store_update_starts_from_the_saved_book_and_keeps_both_changes(tmp_path: Path) -> None:
    store = CategoryStore(tmp_path / CATEGORIES_FILENAME, ["Groceries"])
    stale = store.load()
    groceries_id = stale.categories[0].id
    store.update(lambda book: book.assign_suggested("Żabka", groceries_id))

    store.update(lambda book: book.assign("Biedronka", groceries_id))

    saved = store.load()
    assert saved.is_ai_assigned("Żabka")
    assert saved.category_of("Biedronka") is not None
