"""Logging configuration."""

import logging
import os


def setup_logging() -> None:
    """Configure application logging."""
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
