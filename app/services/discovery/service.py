import logging
import socket
import struct

import app.core.netutils as netutils
from app.core.service_base import BaseService, BackgroundProcessServiceStart


logger = logging.getLogger(__name__)


class DiscoveryServer(object):
    MULTICAST_GROUP = '224.108.73.1'
    SERVER_PORT = 23034

    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.active = True

    def run(self, success_callback=None):
        self.sock.bind(('', self.SERVER_PORT))
        group = socket.inet_aton(self.MULTICAST_GROUP)
        mreq = struct.pack('4sL', group, socket.INADDR_ANY)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        self.sock.settimeout(15)
        if success_callback:
            success_callback()

        while self.active:
            try:
                data, address = self.sock.recvfrom(1024)
            except socket.timeout:
                continue
            msg = data.decode()
            if msg == "QUERY":
                self.sock.sendto("HELLO".encode("UTF-8"), address)

    def stop(self):
        self.active = False


class DiscoveryService(BackgroundProcessServiceStart, BaseService):
    def __init__(self, config):
        self.server = DiscoveryServer()
        super().__init__()

    def get_component_name(self):
        return "discovery"

    def on_service_start(self, *args, **kwargs):
        self.server.run(lambda: self.notify_start())

    def on_service_stop(self):
        self.server.stop()
