"""
This module helps translate commands into UUIDs and back. We need this so that
clients do not work off stale views. Ideally, the refresh operation needs to occur
every time a view changes.
"""

from uuid import uuid4
import logging

from .server import RemoteControlServer


logger = logging.getLogger(__name__)


def build_new_map(actions):
    return {str(uuid4()): action for action in actions}


def serialize_controls(data):
    actions = ",".join("{x[name]};{x[id]}".format(x=act) for act in data)
    return "ITEMS COMM " + actions


def get_controls_data(obj):
    res = []
    for cid, command in obj.items():
        obj = {"name": command["name"], "id": cid}
        res.append(obj)
    return res


class CommandsTranslator(object):

    VERSION = "0.8"

    def __init__(self, service):
        self.service = service
        self.server = RemoteControlServer(self)
        self.map = {}

    def translate_command(self, command_id):
        return self.map.get(command_id)

    def refresh(self):
        actions = self.service.list_commands()
        self.map = build_new_map(actions)
        self.server.send_all(serialize_controls(get_controls_data(self.map)))

    def process(self, line):
        if line == "VERSION":
            return "PISERVER " + self.VERSION
        elif line.startswith("REQUEST"):
            return serialize_controls(get_controls_data(self.map))
        elif line.startswith("EXECUTE"):
            return self.on_command(line.strip().split(" ")[1])
        elif line.startswith("OK"):
            return None
        logger.info("Bad line on TCP server: %s", line.strip())

    def on_command(self, command_id):
        command = self.translate_command(command_id)
        if command is None:
            logger.error("Unable to translate command: %s.", command_id)
            return "BAD"
        return "OK" if self.service.on_command(command["cmd"]) else "BAD"

    def start(self):
        self.map = build_new_map(self.service.list_commands())
        self.server.start()
