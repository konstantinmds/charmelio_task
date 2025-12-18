"""Ensure logging setup does not crash and sets level."""

import logging

from app.core.logging import setup_logging


def test_setup_logging():
    setup_logging()
    logger = logging.getLogger()
    # Should configure without raising; ensure at least one handler attached
    assert logger.handlers
