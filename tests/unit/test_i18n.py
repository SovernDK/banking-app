from collections.abc import Iterator
from string import Formatter

import pytest

from app import texts
from app.i18n import Language, Plural, Text


def _all_texts() -> Iterator[tuple[str, Text | Plural]]:
    for name, value in vars(texts).items():
        if isinstance(value, Text | Plural):
            yield name, value
        elif isinstance(value, dict) and not name.startswith("__"):
            for key, text in value.items():
                yield f"{name}[{key}]", text


def _fields(template: str) -> set[str]:
    return {field for _, field, _, _ in Formatter().parse(template) if field}


@pytest.mark.parametrize(
    ("name", "text"), [pytest.param(name, text, id=name) for name, text in _all_texts()]
)
def test_every_translation_is_filled_in_and_takes_the_same_values(
    name: str, text: Text | Plural
) -> None:
    if isinstance(text, Text):
        forms = list(text.forms().values())
    else:
        forms = [form for variants in text.forms().values() for form in variants]
    assert all(form.strip() for form in forms), name
    assert len({frozenset(_fields(form)) for form in forms}) == 1, name


def test_text_is_shown_in_the_chosen_language_with_values_filled_in() -> None:
    greeting = Text(pl="Cześć {name}", en="Hello {name}", ja="{name}さん、こんにちは")

    assert greeting(Language.PL, name="Ola") == "Cześć Ola"
    assert greeting(Language.EN, name="Ola") == "Hello Ola"
    assert greeting(Language.JA, name="Ola") == "Olaさん、こんにちは"


_FILES = Plural(
    pl=("{count} plik", "{count} pliki", "{count} plików"),
    en=("{count} file", "{count} files"),
    ja="{count}件のファイル",
)


@pytest.mark.parametrize(
    ("language", "count", "expected"),
    [
        (Language.EN, 1, "1 file"),
        (Language.EN, 0, "0 files"),
        (Language.EN, 2, "2 files"),
        (Language.PL, 1, "1 plik"),
        (Language.PL, 2, "2 pliki"),
        (Language.PL, 5, "5 plików"),
        (Language.PL, 12, "12 plików"),
        (Language.PL, 22, "22 pliki"),
        (Language.PL, 0, "0 plików"),
        (Language.JA, 1, "1件のファイル"),
        (Language.JA, 3, "3件のファイル"),
    ],
)
def test_plural_picks_the_form_for_the_count(language: Language, count: int, expected: str) -> None:
    assert _FILES(language, count) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [("pl", Language.PL), ("en", Language.EN), ("ja", Language.JA), ("jp", None), (None, None)],
)
def test_parse_accepts_only_supported_language_codes(
    value: object, expected: Language | None
) -> None:
    assert Language.parse(value) == expected


def test_languages_are_labelled_pl_en_jp() -> None:
    assert [language.label for language in Language] == ["PL", "EN", "JP"]
