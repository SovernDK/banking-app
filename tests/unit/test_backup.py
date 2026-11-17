from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from app.backup import back_up
from app.banking.history import HistoryStore
from app.categories import CATEGORIES_FILENAME, CategoryBook, CategoryStore
from app.database import DATABASE_FILENAME
from app.payments import Payment

DAY = date(2026, 11, 17)


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    path = tmp_path / "data"
    path.mkdir()
    HistoryStore(path / DATABASE_FILENAME).replace_from(
        "account",
        DAY,
        [Payment(payee="Lidl", amount=Decimal("12.50"), currency="PLN", booked_on=DAY)],
    )
    book = CategoryBook()
    book.assign("Lidl", book.create("Groceries").id)
    CategoryStore(path / CATEGORIES_FILENAME, []).save(book)
    return path


def test_backup_holds_the_payment_history_and_category_rules(
    data_dir: Path, tmp_path: Path
) -> None:
    folder = back_up(data_dir, tmp_path / "backups", DAY, keep=14)

    assert folder is not None
    assert [payment.payee for payment in HistoryStore(folder / DATABASE_FILENAME).payments()] == [
        "Lidl"
    ]
    restored = CategoryStore(folder / CATEGORIES_FILENAME, []).load()
    category = restored.category_of("Lidl")
    assert category is not None and category.name == "Groceries"


def test_backup_keeps_only_the_newest_ones(data_dir: Path, tmp_path: Path) -> None:
    backups = tmp_path / "backups"

    for days_ago in range(4, -1, -1):
        back_up(data_dir, backups, DAY - timedelta(days=days_ago), keep=3)

    assert sorted(path.name for path in backups.iterdir()) == [
        "yiji-2026-11-15",
        "yiji-2026-11-16",
        "yiji-2026-11-17",
    ]


def test_second_backup_on_the_same_day_replaces_the_first(data_dir: Path, tmp_path: Path) -> None:
    backups = tmp_path / "backups"
    back_up(data_dir, backups, DAY, keep=14)
    (data_dir / CATEGORIES_FILENAME).unlink()

    folder = back_up(data_dir, backups, DAY, keep=14)

    assert folder is not None
    assert not (folder / CATEGORIES_FILENAME).exists()
    assert len(list(backups.iterdir())) == 1


def test_nothing_is_backed_up_before_the_first_sync(tmp_path: Path) -> None:
    backups = tmp_path / "backups"

    assert back_up(tmp_path / "empty", backups, DAY, keep=14) is None
    assert not backups.exists()
