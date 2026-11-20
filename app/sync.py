"""Stores the latest bank payments and exchange rates without the dashboard open; run daily by
the systemd timer in deploy/systemd."""

import logging
import sys
from enum import IntEnum

from app.ai_categories.client import CategorisationUnavailableError
from app.ai_categories.service import AutoCategoriser
from app.config import Settings
from app.modules import Modules, build_modules
from app.payments import Payment
from app.refresh import BankStatus, Refresher

logger = logging.getLogger("app.sync")


class SyncResult(IntEnum):
    """The process exit code, so the timer's journal shows which runs need attention."""

    SYNCED = 0
    FAILED = 1
    NEEDS_RECONNECT = 2


def sync(refresher: Refresher, auto_categoriser: AutoCategoriser | None = None) -> SyncResult:
    refreshed = refresher.refresh(force=True)
    result = SyncResult.SYNCED
    if refreshed.needs_connection:
        logger.error("Not synced: the bank connection is missing or expired; reconnect in Yiji.")
        result = SyncResult.NEEDS_RECONNECT
    elif refreshed.bank is BankStatus.BANK_UNAVAILABLE:
        logger.error("Not synced: %s", refreshed.bank_error)
        result = SyncResult.FAILED
    if refreshed.rates_error is not None:
        logger.error("Exchange rates not updated: %s", refreshed.rates_error)
        result = max(result, SyncResult.FAILED)
    if auto_categoriser is not None:
        _categorise(auto_categoriser, refreshed.payments)
    if result is SyncResult.SYNCED:
        logger.info("Synced; %d payments stored in total.", len(refreshed.payments))
    return result


def _categorise(auto_categoriser: AutoCategoriser, payments: list[Payment]) -> None:
    # Categories are a convenience the user can always set by hand, so a model outage only
    # logs a warning and leaves the sync result alone.
    try:
        assigned = auto_categoriser.run(payments)
    except CategorisationUnavailableError as error:
        logger.warning("Categories not assigned: %s", error)
        return
    if assigned:
        logger.info("AI assigned categories to %d counterparties.", assigned)


def run(modules: Modules) -> SyncResult:
    if modules.bank is None:
        logger.error("Not synced: Enable Banking credentials are not configured.")
        return SyncResult.FAILED
    return sync(modules.bank.refresher, modules.auto_categoriser)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    # Request URLs carry account ids, which have no place in the system journal.
    logging.getLogger("httpx2").setLevel(logging.WARNING)
    return run(build_modules(Settings()))


if __name__ == "__main__":
    sys.exit(main())
