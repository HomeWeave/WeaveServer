import json
import logging
import socket
import struct
from ipaddress import IPv4Network
from threading import Event

import app.core.netutils as netutils
from app.core.services import BaseService, BackgroundProcessServiceStart


logger = logging.getLogger(__name__)


def get_message_server_address(request_addr):
    for ip_obj in netutils.iter_ipv4_addresses():
        ours = IPv4Network(ip_obj["addr"] + "/" + ip_obj["netmask"],
                           strict=False)
        theirs = IPv4Network(request_addr + "/" + ip_obj["netmask"],
                             strict=False)
        if ours == theirs:
            return {"host": ip_obj["addr"], "port": 11023}
    return None


class DiscoveryServer(object):
    MULTICAST_GROUP = '224.108.73.1'
    SERVER_PORT = 23034
    ACTIVE_POLL_TIME = 15

    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.active = True
        self.exited = Event()

    def run(self, success_callback=None):
        self.sock.setsockopt(socket.IPPROTO_IP, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.MULTICAST_GROUP, self.SERVER_PORT))
        group = socket.inet_aton(self.MULTICAST_GROUP)
        mreq = struct.pack('4sL', group, socket.INADDR_ANY)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
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

        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_DROP_MEMBERSHIP, mreq)
        self.sock.close()
        # del self.sock
        self.exited.set()

    def process(self, address, msg):
        if msg == "QUERY":
            obj = get_message_server_address(address[0]) or {}
            return json.dumps(obj).encode("UTF-8")

    def stop(self):
        self.active = False
        self.exited.wait()


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
