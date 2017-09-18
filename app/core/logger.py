"""
This module helps configure logging app-wide.
"""

import logging.config

from app.core.config_loader import JsonConfig


def configure_logging():
    """ Reads app/configs/logging_config.json to initialize logging config."""
    config = JsonConfig({ "path": "logging_config.json" })
    logging.config.dictConfig(config.get())
