"""
This module implements the basic gevent server that listens to user inputs from
android device.
"""
import logging
import json

import eventlet


logger = logging.getLogger(__name__)


def serialize_controls(data):
    actions = ",".join("{x[name]};{x[id]}".format(x=act) for act in data)
    return "ITEMS COMM " + actions


#class RemoteControlServer(StreamServer):
class RemoteControlServer(object):
    VERSION = "0.8"
    def __init__(self, service, host='0.0.0.0', port=15023):
        self.server = eventlet.listen((host, port))
        self.pool = eventlet.GreenPool()
        self.service = service

    def serve_forever(self):
        while True:
           try:
               new_sock, address = self.server.accept()
               logger.info("Client connected.")
               self.pool.spawn_n(self.on_connection, new_sock.makefile('rw'))
           except (SystemExit, KeyboardInterrupt):
               break

    def on_connection(self, inp):
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
            inp.write(res)
            inp.flush()

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
