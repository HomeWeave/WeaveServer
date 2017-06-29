import logging.config
import logging
import json
import sys


class Redirect(object):
    def __init__(self, name, level):
        self.logger = logging.getLogger(name)
        self.level = level

    def write(self, msg):
        for line in buf.rstrip().splitlines():
            print(line, file=sys.__stdout__)
            self.logger.log(self.level, line.rstrip())

    def flush(self):
        pass


def configure_logging(app):
    with open("app/logging-config.json") as f:
        logging.config.dictConfig(json.load(f))

    for handler in logging.getLogger().handlers:
        print("Adding {}.".format(handler))
        app.logger.addHandler(handler)

    #sys.stdout = Redirect('stdout', logging.INFO)
    #sys.stderr = Redirect('stderr', logging.ERROR)

