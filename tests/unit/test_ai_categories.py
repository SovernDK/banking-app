from datetime import date

import pytest
from pydantic import SecretStr

from app.ai_categories.client import CategorisationUnavailableError
from app.ai_categories.service import AutoCategoriser, build_auto_categoriser
from app.categories import CategoryStore
from app.config import Settings
from app.payment_methods import PaymentMethod
from tests.fakes.ollama import FakeOllamaState
from tests.fakes.payments import payment

DAY = date(2026, 11, 15)


def test_model_fills_in_uncategorised_counterparties_following_the_users_choices(
    auto_categoriser: AutoCategoriser,
    category_store: CategoryStore,
    fake_ollama: FakeOllamaState,
) -> None:
    saved = category_store.load()
    groceries = saved.find_by_name("Groceries")
    assert groceries is not None
    saved.assign("Biedronka", groceries.id)
    category_store.save(saved)
    fake_ollama.categories = {"ŻABKA POLSKA": "Groceries", "Biedronka": "Shopping"}
    payments = [
        payment("4", DAY, payee="Biedronka"),
        payment("9", DAY, payee="ŻABKA POLSKA", name="Zakup kartą 1", method=PaymentMethod.BLIK),
        payment("5", DAY, payee="ŻABKA POLSKA", name="Zakup kartą 1"),
        payment("7", DAY, payee="ŻABKA POLSKA", name="Zakup kartą 2"),
        payment("8", DAY, payee="ŻABKA POLSKA", name="Zakup kartą 3"),
    ]

    assert auto_categoriser.run(payments) == 1

    book = category_store.load()
    assert book.category_of("Żabka Polska") == groceries
    assert book.is_ai_assigned("ŻABKA POLSKA")
    assert book.category_of("Biedronka") == groceries
    [request] = fake_ollama.requests
    [question] = fake_ollama.questions()
    assert question["counterparties"] == [
        {
            "id": "1",
            "name": "ŻABKA POLSKA",
            "payment_titles": ["Zakup kartą 1", "Zakup kartą 2"],
            "payment_method": "BLIK",
        }
    ]
    assert question["examples"] == {"biedronka": "Groceries"}
    assert "Groceries" in question["categories"]
    assert request["format"]["properties"]["1"]["enum"] == [
        *question["categories"],
        None,
    ]


def test_spellings_of_a_name_are_asked_about_once(
    auto_categoriser: AutoCategoriser,
    category_store: CategoryStore,
    fake_ollama: FakeOllamaState,
) -> None:
    fake_ollama.categories = {"Netflix": "Entertainment"}

    assigned = auto_categoriser.run(
        [
            payment("5", DAY, payee="NETFLIX", name="Plan 1"),
            payment("5", DAY, payee="Netflix", name="Plan 2"),
            payment("5", date(2026, 11, 1), payee="Netflix", name="Plan 1"),
        ]
    )

    assert assigned == 1
    [question] = fake_ollama.questions()
    assert [(item["name"], item["payment_titles"]) for item in question["counterparties"]] == [
        ("Netflix", ["Plan 1", "Plan 2"])
    ]
    assert category_store.load().category_of("NETFLIX") is not None


def test_counterparties_are_asked_about_in_batches(
    auto_categoriser: AutoCategoriser,
    category_store: CategoryStore,
    fake_ollama: FakeOllamaState,
) -> None:
    fake_ollama.categories = {"Lidl": "Groceries", "Orlen": "Transport", "Netflix": "Entertainment"}

    assigned = auto_categoriser.run(
        [payment("1", DAY, payee=name) for name in ["Lidl", "Orlen", "Netflix"]]
    )

    assert assigned == 3
    assert [len(question["counterparties"]) for question in fake_ollama.questions()] == [2, 1]
    assert category_store.load().category_of("Netflix") is not None


def test_unsure_or_unknown_answers_leave_counterparties_uncategorised(
    auto_categoriser: AutoCategoriser,
    category_store: CategoryStore,
    fake_ollama: FakeOllamaState,
) -> None:
    fake_ollama.raw_content = '{"1": null, "2": "Crypto", "3": "Groceries", "Kantor": "Groceries"}'

    assigned = auto_categoriser.run(
        [payment("1", DAY, payee="Jan Kowalski"), payment("2", DAY, payee="Kantor")]
    )

    book = category_store.load()
    assert assigned == 0
    assert book.rules == {}


def test_answer_wrapped_in_a_markdown_code_block_is_still_read(
    auto_categoriser: AutoCategoriser,
    category_store: CategoryStore,
    fake_ollama: FakeOllamaState,
) -> None:
    """Ollama Cloud models ignore the requested schema and fence their JSON in ```json."""
    fake_ollama.raw_content = '```json\n{"1": "Groceries"}\n```'

    assert auto_categoriser.run([payment("1", DAY, payee="Lidl")]) == 1
    assert category_store.load().is_ai_assigned("Lidl")


def test_nothing_is_asked_when_every_counterparty_has_a_category_or_there_are_no_categories(
    auto_categoriser: AutoCategoriser,
    category_store: CategoryStore,
    fake_ollama: FakeOllamaState,
) -> None:
    category_store.update(lambda book: book.assign("Lidl", book.categories[0].id))
    assert auto_categoriser.run([payment("1", DAY, payee="Lidl"), payment("2", DAY)]) == 0

    category_store.update(
        lambda book: [book.delete(category.id) for category in list(book.categories)]
    )
    assert auto_categoriser.run([payment("1", DAY, payee="Orlen")]) == 0

    assert fake_ollama.requests == []


@pytest.mark.parametrize(
    ("failure_status", "raw_content"),
    [(503, None), (None, "not json"), (None, '{"1": 1}'), (None, '[{"1": "Groceries"}]')],
)
def test_model_outage_or_bad_answer_is_reported(
    auto_categoriser: AutoCategoriser,
    fake_ollama: FakeOllamaState,
    failure_status: int | None,
    raw_content: str | None,
) -> None:
    fake_ollama.failure_status = failure_status
    fake_ollama.raw_content = raw_content

    with pytest.raises(CategorisationUnavailableError):
        auto_categoriser.run([payment("1", DAY, payee="Lidl")])


def test_ai_categories_are_off_without_an_ollama_key(settings: Settings) -> None:
    assert build_auto_categoriser(settings) is None
    with_key = settings.model_copy(update={"ollama_api_key": SecretStr("key")})
    assert build_auto_categoriser(with_key) is not None
