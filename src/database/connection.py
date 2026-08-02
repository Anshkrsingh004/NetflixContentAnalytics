"""SQLite connection helper (Milestone 5).

Provides a single, reusable way to open the project database so that every
consumer (the loader, the SQL analytics layer in M6, the dashboard) shares the
same settings — most importantly ``PRAGMA foreign_keys = ON``, which SQLite
requires *per connection* to actually enforce foreign keys.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from src import config
from src.logger import get_logger

log = get_logger(__name__)


@contextmanager
def get_connection(
    db_path: Path = config.DATABASE_PATH, *, row_factory: bool = False
) -> Iterator[sqlite3.Connection]:
    """Yield a SQLite connection with foreign keys enabled.

    Commits on success, rolls back on error, and always closes the connection.

    Parameters
    ----------
    db_path:
        Location of the SQLite file (defaults to the project database).
    row_factory:
        If True, rows are returned as ``sqlite3.Row`` (dict-like access by
        column name) — handy for the analytics layer and dashboard.
    """
    config.ensure_directories()
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    if row_factory:
        conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        log.exception("Database transaction failed; rolled back.")
        raise
    finally:
        conn.close()
