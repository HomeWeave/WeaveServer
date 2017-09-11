"""
This module helps configure logging app-wide.
"""

import logging.config
import logging
import json


def configure_logging(logger=None):
    """ Reads app/logging-config.json to initialize logging config."""
    with open("app/logging-config.json") as json_file:
        logging.config.dictConfig(json.load(json_file))

    if logger is not None:
        for handler in logging.getLogger().handlers:
            logger.addHandler(handler)
