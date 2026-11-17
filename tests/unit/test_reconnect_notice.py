import pytest

from app.i18n import Language
from app.ui.components.reconnect_notice import ends_in_text


@pytest.mark.parametrize(
    ("days", "language", "expected"),
    [
        (0, Language.EN, "Your bank connection ends today."),
        (1, Language.EN, "Your bank connection ends in 1 day."),
        (7, Language.EN, "Your bank connection ends in 7 days."),
        (0, Language.PL, "Połączenie z bankiem wygasa dziś."),
        (3, Language.PL, "Połączenie z bankiem wygasa za 3 dni."),
    ],
)
def test_notice_counts_the_days_left_and_says_today_on_the_last_one(
    days: int, language: Language, expected: str
) -> None:
    assert ends_in_text(language, days) == expected
