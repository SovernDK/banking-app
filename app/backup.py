"""Copies the payment history and categories into a dated folder, keeping the newest few; run
after the daily sync by the systemd timer in deploy/systemd. Banks serve only the last months, so
the history older than that exists nowhere else."""

import logging
import shutil
import sqlite3
import sys
import tempfile
from contextlib import closing
from datetime import date
from pathlib import Path

from app.categories import CATEGORIES_FILENAME
from app.config import get_settings
from app.database import DATABASE_FILENAME, connect

logger = logging.getLogger("app.backup")


def back_up(data_dir: Path, backup_dir: Path, today: date, keep: int) -> Path | None:
    """The folder written, or None before the first sync has stored anything."""
    database = data_dir / DATABASE_FILENAME
    if not database.exists():
        return None
    backup_dir.mkdir(parents=True, exist_ok=True)
    folder = backup_dir / f"yiji-{today.isoformat()}"
    # Built aside and moved in whole, so a failed run never leaves a half-written backup.
    staging = Path(tempfile.mkdtemp(dir=backup_dir, prefix=".staging-"))
    try:
        # SQLite's backup API copies a consistent snapshot even while the app is writing.
        with (
            connect(database) as source,
            closing(sqlite3.connect(staging / DATABASE_FILENAME)) as target,
        ):
            source.backup(target)
        categories = data_dir / CATEGORIES_FILENAME
        if categories.exists():
            shutil.copy2(categories, staging / CATEGORIES_FILENAME)
        shutil.rmtree(folder, ignore_errors=True)
        staging.rename(folder)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    for old in sorted(backup_dir.glob("yiji-*"))[:-keep]:
        shutil.rmtree(old)
    return folder


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = get_settings()
    folder = back_up(settings.data_dir, settings.backup_dir, date.today(), settings.backup_keep)
    if folder is None:
        logger.info("Nothing to back up yet.")
    else:
        logger.info("Backed up to %s.", folder)
    return 0


if __name__ == "__main__":
    sys.exit(main())
