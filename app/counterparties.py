from collections import defaultdict
from collections.abc import Iterable
from datetime import date

from app.payments import Payment, counterparty_name, squash_spaces


def counterparty_key(name: str) -> str:
    """The same for two counterparty names that differ only in letter case or spacing."""
    return squash_spaces(name).casefold()


class Counterparties:
    """Shows every spelling of a counterparty name as the one used on the most payments, the
    newest breaking a tie. Counting payments rather than amounts keeps the choice the same
    whatever currency the payments are in."""

    def __init__(self, payments: Iterable[Payment]) -> None:
        usage: dict[str, dict[str, tuple[int, date]]] = defaultdict(dict)
        for payment in payments:
            name = counterparty_name(payment)
            if name is None:
                continue
            spellings = usage[counterparty_key(name)]
            count, newest = spellings.get(name, (0, payment.booked_on))
            spellings[name] = (count + 1, max(newest, payment.booked_on))
        self._labels = {
            key: max(spellings, key=spellings.__getitem__) for key, spellings in usage.items()
        }

    def label(self, name: str) -> str:
        """The spelling to show for `name`; a name no payment went to is shown as given."""
        return self._labels.get(counterparty_key(name), name)
