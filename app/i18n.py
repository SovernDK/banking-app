from dataclasses import dataclass
from enum import StrEnum


class Language(StrEnum):
    """Values are ISO 639-1 codes, so they also serve as the page's `lang` attribute."""

    PL = "pl"
    EN = "en"
    JA = "ja"

    @property
    def label(self) -> str:
        return _LABELS[self]

    @classmethod
    def parse(cls, value: object) -> "Language | None":
        try:
            return cls(value)
        except ValueError:
            return None


_LABELS = {Language.PL: "PL", Language.EN: "EN", Language.JA: "JP"}


@dataclass(frozen=True)
class Text:
    """One piece of UI text in every language; `{name}` fields are filled in when it is shown."""

    pl: str
    en: str
    ja: str

    def __call__(self, language: Language, **values: object) -> str:
        return self.forms()[language].format(**values)

    def forms(self) -> dict[Language, str]:
        return {Language.PL: self.pl, Language.EN: self.en, Language.JA: self.ja}


@dataclass(frozen=True)
class Plural:
    """Text that changes with `{count}`, in each language's plural forms (CLDR rules)."""

    pl: tuple[str, str, str]
    """one (1), few (2-4, 22-24, …), many (0, 5-21, 25-31, …)."""
    en: tuple[str, str]
    """one (1), other."""
    ja: str
    """Japanese nouns have no plural."""

    def __call__(self, language: Language, count: int, **values: object) -> str:
        return self._form(language, count).format(count=count, **values)

    def forms(self) -> dict[Language, tuple[str, ...]]:
        return {Language.PL: self.pl, Language.EN: self.en, Language.JA: (self.ja,)}

    def _form(self, language: Language, count: int) -> str:
        if language is Language.JA:
            return self.ja
        if language is Language.EN:
            one, other = self.en
            return one if count == 1 else other
        one, few, many = self.pl
        if count == 1:
            return one
        if count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
            return few
        return many
