"""
This module helps configure logging app-wide.
"""

import logging.config
import logging
import json


class Redirect(object):
    """Redirects all write to a file-like object to a logger."""
    def __init__(self, name, level):
        self.logger = logging.getLogger(name)
        self.level = level

    def write(self, msg):
        for line in msg.rstrip().splitlines():
            #print(line, file=sys.__stdout__)
            self.logger.log(self.level, line.rstrip())

    def flush(self):
        pass


def configure_logging(app):
    """ Reads app/logging-config.json to initialize logging config."""
    with open("app/logging-config.json") as json_file:
        logging.config.dictConfig(json.load(json_file))

    for handler in logging.getLogger().handlers:
        app.logger.addHandler(handler)

    #sys.stdout = Redirect('stdout', logging.INFO)
    #sys.stderr = Redirect('stderr', logging.ERROR)

