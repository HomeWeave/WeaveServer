"""
This module implements the basic gevent server that listens to user inputs from
android device.
"""
import logging
import json

from gevent.server import StreamServer


logger = logging.getLogger(__name__)


def serialize_controls(data):
    actions = ",".join("{x[name]};{x[id]}".format(x=act) for act in data)
    return "ITEMS COMM " + actions


class RemoteControlServer(StreamServer):
    VERSION = "0.8"
    def __init__(self, service, host='0.0.0.0', port=15023):
        super().__init__((host, port), self.on_connection)
        self.service = service

    def on_connection(self, socket, addr):
        inp = socket.makefile(mode='r')
        while True:
            line = inp.readline()
            if not line:
                logger.info("RemoteControl client disconnected.")
                break
            res = self.process(line)

            if not res:
                continue

            res = res.rstrip() + "\n"
            logger.info("Sending: " + res.strip() + " for " + line)
            socket.sendall(res.encode())

    def process(self, line):
        if line.strip() == "VERSION":
            return "PISERVER " + self.VERSION
        elif line.strip().startswith("REQUEST"):
            return serialize_controls(self.service.get_controls())
        elif line.strip().startswith("EXECUTE"):
            return self.service.on_command(line.strip().split(" ")[1])
        elif line.strip().startswith("OK"):
            pass
        logger.info("Bad line on TCP server: %s", line.strip())
