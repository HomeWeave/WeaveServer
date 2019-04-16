import json
import logging
import socket
from threading import Event

from ipaddress import IPv4Network

import weavelib.netutils as netutils


logger = logging.getLogger(__name__)


def get_message_server_address(request_addr):
    addr = netutils.relevant_ipv4_address(request_addr)
    if addr is not None:
        return {"host": addr, "port": 11023}
    return None


class DiscoveryServer(object):
    SERVER_PORT = 23034
    ACTIVE_POLL_TIME = 15

    def __init__(self, message_server_port):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.active = True

    def run(self, success_callback=None):
        self.sock.bind(('', self.SERVER_PORT))
        self.sock.settimeout(self.ACTIVE_POLL_TIME)
        if success_callback:
            success_callback()

        while self.active:
            try:
                data, address = self.sock.recvfrom(1024)
            except socket.timeout:
                continue
            msg = data.decode()
            res = self.process(address, msg)
            if res:
                self.sock.sendto(res, address)

        self.sock.close()

    def process(self, address, msg):
        if msg == "QUERY":
            obj = get_message_server_address(address[0]) or {}
            return json.dumps(obj).encode("UTF-8")

    def stop(self):
        self.active = False
