"""
This module helps configure logging app-wide.
"""

import logging.config

from weaveserver.core.config_loader import PyConfig


def configure_logging():
    """ Reads app/configs/logging_config.py to initialize logging config."""
    config = PyConfig({"file": "logging_config.py"})
    logging.config.dictConfig(config["LOGGING"])
