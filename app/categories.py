import itertools
import logging
import uuid
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Annotated, TypeVar

from pydantic import BaseModel, Field, StringConstraints, TypeAdapter, ValidationError

from app.counterparties import counterparty_key
from app.json_file import write_atomically
from app.payments import squash_spaces

logger = logging.getLogger(__name__)

T = TypeVar("T")


CategoryName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]


class InvalidCategoryNameError(ValueError):
    pass


class DuplicateCategoryError(ValueError):
    def __init__(self, name: str) -> None:
        super().__init__(f"A category named {name} already exists.")
        self.name = name


def _name_key(name: str) -> str:
    return squash_spaces(name).casefold()


def _valid_name(name: str) -> str:
    try:
        return squash_spaces(TypeAdapter(CategoryName).validate_python(name))
    except ValidationError as error:
        raise InvalidCategoryNameError("A category name needs 1 to 40 characters.") from error


class Category(BaseModel):
    id: str
    name: CategoryName
    colour_slot: int | None = Field(default=None, ge=0)


class CategoryBook(BaseModel):
    categories: list[Category] = []
    rules: dict[str, str] = Field(
        default={}, description="Counterparty name match key to category id."
    )
    ai_assigned: set[str] = Field(
        default=set(), description="Match keys whose rule an AI model chose, not the user."
    )

    def get(self, category_id: str) -> Category | None:
        return next((category for category in self.categories if category.id == category_id), None)

    def find_by_name(self, name: str) -> Category | None:
        key = _name_key(name)
        return next(
            (category for category in self.categories if _name_key(category.name) == key), None
        )

    def create(self, name: str) -> Category:
        name = _valid_name(name)
        if self.find_by_name(name):
            raise DuplicateCategoryError(name)
        category = Category(id=uuid.uuid4().hex, name=name)
        self.categories.append(category)
        return category

    def rename(self, category_id: str, name: str) -> None:
        category = self._require(category_id)
        name = _valid_name(name)
        same_name = self.find_by_name(name)
        if same_name and same_name.id != category_id:
            raise DuplicateCategoryError(name)
        category.name = name

    def usage(self, category_id: str) -> int:
        return sum(1 for assigned in self.rules.values() if assigned == category_id)

    def delete(self, category_id: str) -> None:
        self._require(category_id)
        self.categories = [category for category in self.categories if category.id != category_id]
        self.rules = {
            key: assigned for key, assigned in self.rules.items() if assigned != category_id
        }
        self.ai_assigned &= self.rules.keys()

    def assign(self, counterparty: str, category_id: str | None) -> None:
        key = counterparty_key(counterparty)
        self.ai_assigned.discard(key)
        if category_id is None:
            self.rules.pop(key, None)
            return
        category = self._require(category_id)
        self.rules[key] = category_id
        self._give_colour(category)

    def assign_choice(self, counterparty: str, choice: str | None) -> None:
        """Assigns what the person picked: a category id, the name of an existing category, or
        a new name, which creates the category; None makes the name uncategorised."""
        if choice is None or self.get(choice):
            self.assign(counterparty, choice)
            return
        existing = self.find_by_name(choice)
        self.assign(counterparty, (existing or self.create(choice)).id)

    def assign_suggested(self, counterparty: str, category_id: str) -> bool:
        """Applies an AI model's choice unless the name already has a category; tells whether
        it did."""
        key = counterparty_key(counterparty)
        if key in self.rules:
            return False
        category = self._require(category_id)
        self.rules[key] = category_id
        self.ai_assigned.add(key)
        self._give_colour(category)
        return True

    def is_ai_assigned(self, counterparty: str) -> bool:
        return counterparty_key(counterparty) in self.ai_assigned

    def category_of(self, counterparty: str | None) -> Category | None:
        if counterparty is None:
            return None
        category_id = self.rules.get(counterparty_key(counterparty))
        return self.get(category_id) if category_id else None

    def _give_colour(self, category: Category) -> None:
        # Colours go only to categories in use, so unused ones never crowd the palette, and a
        # category keeps its colour as long as no other category in use already has it.
        taken = {
            other.colour_slot
            for other in self.categories
            if other.id != category.id and self.usage(other.id)
        }
        if category.colour_slot is None or category.colour_slot in taken:
            category.colour_slot = next(slot for slot in itertools.count() if slot not in taken)

    def _require(self, category_id: str) -> Category:
        category = self.get(category_id)
        if category is None:
            raise KeyError(category_id)
        return category


class CategoryStore:
    def __init__(self, path: Path, starter_names: Sequence[str]) -> None:
        self._path = path
        self._starter_names = starter_names

    def load(self) -> CategoryBook:
        try:
            return CategoryBook.model_validate_json(self._path.read_bytes())
        except FileNotFoundError:
            book = CategoryBook()
            for name in self._starter_names:
                book.create(name)
            self.save(book)
            return book
        except ValidationError:
            logger.warning("Ignoring unreadable categories at %s", self._path)
            return CategoryBook()

    def save(self, book: CategoryBook) -> None:
        write_atomically(self._path, book.model_dump_json())

    def update(self, change: Callable[[CategoryBook], T]) -> T:
        """Applies `change` to the stored book, saves it and returns what `change` returned.
        The dashboard and the daily sync both write categories, so a change starts from the
        file, never from a stale copy."""
        book = self.load()
        result = change(book)
        self.save(book)
        return result
