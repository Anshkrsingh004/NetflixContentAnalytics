"""Reusable logging setup for the Netflix Content Analytics Platform.

Modules should obtain a logger with ``get_logger(__name__)`` instead of using
``print()``. This gives consistent, timestamped, leveled output that goes to
both the console (for interactive work) and a rotating file under ``logs/``
(for an auditable record of every pipeline run).

Example
-------
>>> from src.logger import get_logger
>>> log = get_logger(__name__)
>>> log.info("Loaded %d rows", 8807)
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from src import config

# One shared format for every handler keeps logs easy to scan and to parse.
# Example line:
# 2026-08-03 14:05:01 | INFO     | src.cleaning.pipeline | Loaded 8807 rows
_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def get_logger(name: str) -> logging.Logger:
    """Return a logger configured to write to the console and a rotating file.

    Parameters
    ----------
    name:
        Usually ``__name__`` of the calling module so each log line reveals
        where it came from.

    Returns
    -------
    logging.Logger
        A ready-to-use logger. Handlers are attached only once per logger name
        so importing a module several times never produces duplicate lines.
    """
    logger = logging.getLogger(name)

    # Guard against double configuration. Python caches loggers by name, so if
    # we have already attached handlers to this logger we return it unchanged —
    # otherwise every message would be emitted once per handler copy.
    if logger.handlers:
        return logger

    logger.setLevel(config.LOG_LEVEL)
    formatter = logging.Formatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # 1) Console handler — human-friendly output while developing.
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 2) Rotating file handler — durable audit trail. Each file caps at 5 MB
    #    and we keep 3 rotated backups, so logs never grow without bound.
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        filename=config.LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Do not bubble records up to the root logger; that would double-print if
    # some other library has configured the root logger.
    logger.propagate = False

    return logger


if __name__ == "__main__":
    # Manual smoke test: emit one line at each level.
    demo = get_logger("logger_smoke_test")
    demo.debug("This DEBUG line is hidden at the default INFO level.")
    demo.info("Logging is configured correctly.")
    demo.warning("This is a warning example.")
    demo.error("This is an error example.")
    print(f"\nCheck the log file at: {config.LOG_FILE}")
