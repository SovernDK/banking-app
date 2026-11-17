"""Stores the latest bank payments and exchange rates without the dashboard open; run daily by
the systemd timer in deploy/systemd."""

import logging
import sys
from enum import IntEnum

from app.banking.client import BankApiError, BankSessionExpiredError
from app.banking.service import BankingService, NotConnectedError, find_banking_service
from app.rates.client import RatesUnavailableError

logger = logging.getLogger("app.sync")


class SyncResult(IntEnum):
    """The process exit code, so the timer's journal shows which runs need attention."""

    SYNCED = 0
    FAILED = 1
    NEEDS_RECONNECT = 2


def sync(service: BankingService) -> SyncResult:
    result = SyncResult.SYNCED
    try:
        service.refresh(force=True)
    except (NotConnectedError, BankSessionExpiredError):
        logger.error("Not synced: the bank connection is missing or expired; reconnect in Yiji.")
        result = SyncResult.NEEDS_RECONNECT
    except BankApiError as error:
        logger.error("Not synced: %s", error)
        result = SyncResult.FAILED
    payments = service.payments()
    try:
        service.refresh_rates(payments)
    except RatesUnavailableError as error:
        logger.error("Exchange rates not updated: %s", error)
        result = max(result, SyncResult.FAILED)
    if result is SyncResult.SYNCED:
        logger.info("Synced; %d payments stored in total.", len(payments))
    return result


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    # Request URLs carry account ids, which have no place in the system journal.
    logging.getLogger("httpx2").setLevel(logging.WARNING)
    service = find_banking_service()
    if service is None:
        logger.error("Not synced: Enable Banking credentials are not configured.")
        return SyncResult.FAILED
    return sync(service)


if __name__ == "__main__":
    sys.exit(main())
