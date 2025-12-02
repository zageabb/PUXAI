"""Logging configuration utilities for the Local Assistant application."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Final

DEFAULT_LOG_LEVEL: Final = "INFO"
LOG_FORMAT: Final = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
LOG_DATEFMT: Final = "%Y-%m-%d %H:%M:%S"


def setup_logging(app_name: str) -> None:
    """Configure root logging with console and file handlers.

    The log level can be overridden by setting the ``APP_LOG_LEVEL`` environment
    variable. Logs are emitted to stdout and to ``./logs/app.log``.

    Args:
        app_name: Name of the application for context in log messages.
    """

    log_level_name = os.getenv("APP_LOG_LEVEL", DEFAULT_LOG_LEVEL).upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    logging.basicConfig(level=log_level, format=LOG_FORMAT, datefmt=LOG_DATEFMT)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(logs_dir / "app.log")
    file_handler.setLevel(log_level)
    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATEFMT)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    root_logger.info("Logging initialized for %s at level %s", app_name, log_level_name)

