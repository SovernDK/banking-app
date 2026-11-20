import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import httpx2
from pydantic import BaseModel, TypeAdapter, ValidationError

from app.config import Thinking
from app.payment_methods import PaymentMethod

INSTRUCTIONS = """\
You sort a person's bank payments into their spending categories. Each counterparty comes from \
a Polish or international bank statement: a shop, company, service or person, with sample \
payment titles and the payment method. Pick exactly one category from `categories` for every \
counterparty in `counterparties`, and follow the person's own choices in `examples`. Answer null \
when nothing gives a reasonable clue, for example a private person's name. Answer with only a \
JSON object mapping every counterparty id to its category or null, for example \
{"1": "Groceries", "2": null}."""

# Ollama Cloud models ignore the `format` schema and often fence their JSON in a markdown block.
_CODE_FENCE = re.compile(r"\s*```(?:json)?\s*(.*?)\s*```\s*", re.DOTALL)
_ANSWER = TypeAdapter(dict[str, str | None])


class CategorisationUnavailableError(Exception):
    pass


@dataclass(frozen=True)
class CounterpartySample:
    name: str
    titles: tuple[str, ...]
    payment_method: PaymentMethod


class _Message(BaseModel):
    content: str


class _ChatResponse(BaseModel):
    message: _Message


class OllamaCategoriser:
    """Asks a model on the Ollama chat API (Ollama Cloud or a local Ollama) for categories."""

    def __init__(self, http: httpx2.Client, model: str, thinking: Thinking) -> None:
        self._http = http
        self._model = model
        self._thinking = thinking

    def suggest(
        self,
        counterparties: Sequence[CounterpartySample],
        categories: Sequence[str],
        examples: Mapping[str, str],
    ) -> dict[str, str]:
        """The category name chosen for each counterparty name; names the model left out or
        answered with an unknown category are missing."""
        # Models copy long company names inexactly ("Z O O." for "Z O.O."), so they answer by id.
        by_id = {str(number): sample for number, sample in enumerate(counterparties, start=1)}
        question = {
            "categories": list(categories),
            "examples": dict(examples),
            "counterparties": [
                {
                    "id": counterparty_id,
                    "name": sample.name,
                    "payment_titles": list(sample.titles),
                    "payment_method": sample.payment_method.value,
                }
                for counterparty_id, sample in by_id.items()
            ],
        }
        try:
            response = self._http.post(
                "/api/chat",
                json={
                    "model": self._model,
                    "stream": False,
                    "think": False if self._thinking == "off" else self._thinking,
                    "options": {"temperature": 0},
                    "format": _answer_schema(list(by_id), categories),
                    "messages": [
                        {"role": "system", "content": INSTRUCTIONS},
                        {"role": "user", "content": json.dumps(question, ensure_ascii=False)},
                    ],
                },
            )
            response.raise_for_status()
        except httpx2.HTTPError as error:
            raise CategorisationUnavailableError("The AI model could not be reached.") from error
        try:
            content = _ChatResponse.model_validate_json(response.content).message.content
            fenced = _CODE_FENCE.fullmatch(content)
            answer = _ANSWER.validate_json(fenced.group(1) if fenced else content)
        except ValidationError as error:
            raise CategorisationUnavailableError("The AI model returned bad data.") from error
        return {
            by_id[counterparty_id].name: category
            for counterparty_id, category in answer.items()
            if counterparty_id in by_id and category is not None and category in categories
        }


def _answer_schema(ids: Sequence[str], categories: Sequence[str]) -> dict[str, object]:
    return {
        "type": "object",
        "properties": {counterparty_id: {"enum": [*categories, None]} for counterparty_id in ids},
        "required": list(ids),
    }
