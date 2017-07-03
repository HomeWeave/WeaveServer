"""
This module implements the basic gevent server that listens to user inputs from
android device.
"""
import logging
import json

from gevent.server import StreamServer


logger = logging.getLogger(__name__)


class RemoteControlServer(StreamServer):
    VERSION = "0.8"
    def __init__(self, listener, host='0.0.0.0', port=15023):
        super().__init__((host, port), self.on_connection)
        #self.listener = listener

    def on_connection(self, socket, addr):
        inp = socket.makefile(mode='r')
        while True:
            line = inp.readline()
            if not line:
                logger.info("RemoteControl client disconnected.")
                break
            res = self.process(line).rstrip() + "\n"
            socket.sendall(res.encode())

    #def set_listener(self, listener):
    #    self.listener = listener

    def process(self, line):
        if line.strip() == "VERSION":
            return "PISERVER " + self.VERSION
        elif line.strip().startswith("REQUEST"):
            return serialize_controls(self.listener.get_controls())
        return "BAD"
