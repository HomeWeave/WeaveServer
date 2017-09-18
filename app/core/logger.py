"""
This module helps configure logging app-wide.
"""

import logging.config

from app.core.config_loader import get_config


def configure_logging():
    """ Reads app/configs/logging_config.json to initialize logging config."""
    config = get_config("logging", {"config.json": "simple"})
    logging.config.dictConfig(config)
