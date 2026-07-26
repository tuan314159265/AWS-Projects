"""
Configure application-wide logging.

This module initializes the logging configuration for the entire application.
It should be invoked exactly once during application startup.

Example:
    >>> from core.logger import setup_logging
    >>> setup_logging()
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Log directory
import os
if os.environ.get("LAMBDA_TASK_ROOT"):
    LOG_DIR = Path("/tmp/logs")
else:
    LOG_DIR = PROJECT_ROOT / "logs"

LOG_DIR.mkdir(parents=True, exist_ok=True)

# Default log file
LOG_FILE = LOG_DIR / "application.log"


def setup_logging(
    level: int = logging.INFO,
    log_file: Path = LOG_FILE,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
) -> None:
    """
    Configure the root logger.

    This function should be called only once when the application starts.
    All modules can then retrieve their own logger using:

        logger = logging.getLogger(__name__)

    Args:
        level:
            Minimum logging level.

        log_file:
            Destination log file.

        max_bytes:
            Maximum size of a log file before rotation.

        backup_count:
            Number of rotated log files to keep.
    """
    root_logger = logging.getLogger()

    # Prevent duplicate handlers.
    if root_logger.handlers:
        return

    root_logger.setLevel(level)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console output
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)

    # Rotating log file
    file_handler = RotatingFileHandler(
        filename=log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

def get_logger(name: str) -> logging.Logger:
    """
    Return a logger.

    Parameters
    ----------
    name:
        Usually __name__.

    Returns
    -------
    logging.Logger
    """
    setup_logging()
    return logging.getLogger(name)
