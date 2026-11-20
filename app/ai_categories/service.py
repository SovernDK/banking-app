import functools
from collections.abc import Sequence
from dataclasses import replace

import httpx2

from app.ai_categories.client import CounterpartySample, OllamaCategoriser
from app.categories import CategoryBook, CategoryStore
from app.config import Settings
from app.counterparties import Counterparties
from app.payments import Payment, counterparty_name, name_key


def uncategorised_samples(
    book: CategoryBook, payments: Sequence[Payment], titles_per_name: int
) -> list[CounterpartySample]:
    """Each counterparty without a category, with a few of its distinct payment titles."""
    names = Counterparties(payments)
    samples: dict[str, CounterpartySample] = {}
    for payment in payments:
        name = counterparty_name(payment)
        if name is None or book.category_of(name) is not None:
            continue
        key = name_key(name)
        sample = samples.setdefault(
            key, CounterpartySample(names.label(name), (), payment.payment_method)
        )
        if (
            payment.name
            and payment.name not in sample.titles
            and len(sample.titles) < titles_per_name
        ):
            samples[key] = replace(sample, titles=(*sample.titles, payment.name))
    return list(samples.values())


def _chosen_by_user(book: CategoryBook, limit: int) -> dict[str, str]:
    examples: dict[str, str] = {}
    for key, category_id in book.rules.items():
        category = book.get(category_id)
        if len(examples) >= limit:
            break
        if category is not None and key not in book.ai_assigned:
            examples[key] = category.name
    return examples


def _apply(book: CategoryBook, chosen: dict[str, str]) -> int:
    assigned = 0
    for counterparty, category_name in chosen.items():
        # The user may have renamed or deleted the category while the model was thinking.
        category = book.find_by_name(category_name)
        if category is not None and book.assign_suggested(counterparty, category.id):
            assigned += 1
    return assigned


class AutoCategoriser:
    """Fills in categories for counterparties that have none; a category the user chose is
    never changed."""

    def __init__(
        self,
        categoriser: OllamaCategoriser,
        store: CategoryStore,
        batch_size: int,
        max_examples: int,
        titles_per_name: int,
    ) -> None:
        self._categoriser = categoriser
        self._store = store
        self._batch_size = batch_size
        self._max_examples = max_examples
        self._titles_per_name = titles_per_name

    def run(self, payments: Sequence[Payment]) -> int:
        """How many counterparties got a category. Each batch is saved as soon as it is
        answered, so a failure part way keeps the earlier batches.

        Raises CategorisationUnavailableError when the model cannot be asked."""
        book = self._store.load()
        samples = uncategorised_samples(book, payments, self._titles_per_name)
        if not samples or not book.categories:
            return 0
        categories = [category.name for category in book.categories]
        examples = _chosen_by_user(book, self._max_examples)
        assigned = 0
        for start in range(0, len(samples), self._batch_size):
            batch = samples[start : start + self._batch_size]
            chosen = self._categoriser.suggest(batch, categories, examples)
            assigned += self._store.update(functools.partial(_apply, chosen=chosen))
        return assigned


def build_auto_categoriser(settings: Settings, store: CategoryStore) -> AutoCategoriser | None:
    """None when no Ollama key is configured: categories are then assigned only by hand."""
    if settings.ollama_api_key is None:
        return None
    http = httpx2.Client(
        base_url=str(settings.ollama_api_url),
        timeout=settings.ai_category_timeout_seconds,
        headers={"Authorization": f"Bearer {settings.ollama_api_key.get_secret_value()}"},
    )
    return AutoCategoriser(
        OllamaCategoriser(http, settings.ai_category_model, settings.ai_category_thinking),
        store,
        batch_size=settings.ai_category_batch_size,
        max_examples=settings.ai_category_examples,
        titles_per_name=settings.ai_category_titles_per_name,
    )
