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

from app.config import Settings
from app.database import connect
from app.modules import DataFiles

logger = logging.getLogger("app.backup")


def back_up(files: DataFiles, backup_dir: Path, today: date, keep: int) -> Path | None:
    """The folder written, or None before the first sync has stored anything. The bank
    connection is left out: it is renewed by reconnecting, while the history is not."""
    if not files.database.exists():
        return None
    backup_dir.mkdir(parents=True, exist_ok=True)
    folder = backup_dir / f"yiji-{today.isoformat()}"
    # Built aside and moved in whole, so a failed run never leaves a half-written backup.
    staging = Path(tempfile.mkdtemp(dir=backup_dir, prefix=".staging-"))
    try:
        # SQLite's backup API copies a consistent snapshot even while the app is writing.
        with (
            connect(files.database) as source,
            closing(sqlite3.connect(staging / files.database.name)) as target,
        ):
            source.backup(target)
        if files.categories.exists():
            shutil.copy2(files.categories, staging / files.categories.name)
        shutil.rmtree(folder, ignore_errors=True)
        staging.rename(folder)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    for old in sorted(backup_dir.glob("yiji-*"))[:-keep]:
        shutil.rmtree(old)
    return folder


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = Settings()
    folder = back_up(
        DataFiles.under(settings.data_dir), settings.backup_dir, date.today(), settings.backup_keep
    )
    if folder is None:
        logger.info("Nothing to back up yet.")
    else:
        logger.info("Backed up to %s.", folder)
    return 0


if __name__ == "__main__":
    sys.exit(main())
