import os
import json

from .core.logger import configure_logging
from .core.messaging import MessageServer


def get_password():
    if "REDIS_PASSWD" in os.environ:
        return os.environ["REDIS_PASSWD"]
    with open("/home/rpi/.variables") as f:
        line = next(x.strip() for x in f if x.startswith("REDIS_PASSWD"))
        return line.split("=")[1]


def create_app(config=None):
    configure_logging()
    if config is None:
        config = {
            "host": "alarmpi",
            "password": get_password()
        }

    with open("app/queues.json") as queue_file:
        return MessageServer(6668, config, json.load(queue_file))
