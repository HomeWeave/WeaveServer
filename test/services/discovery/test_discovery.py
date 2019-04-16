import json
import socket
from threading import Event, Thread

import pytest
import weavelib.netutils as netutils

from messaging.discovery import DiscoveryServer


class TestDiscoveryService(object):
    @classmethod
    def setup_class(cls):
        DiscoveryServer.ACTIVE_POLL_TIME = 1
        cls.server = DiscoveryServer(11023)
        event = Event()
        Thread(target=cls.server.run, args=(event.set,)).start()
        event.wait()

    @classmethod
    def teardown_class(cls):
        cls.server.stop()

    def test_bad_query(self):
        ip_addr, port = "<broadcast>", 23034
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client.bind(('', 0))
        client.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        client.sendto("BAD_QUERY".encode('UTF-8'), (ip_addr, port))

        client.settimeout(3)
        with pytest.raises(socket.timeout):
            client.recvfrom(1024)

    def test_no_machine_addresses(self):
        backup = netutils.iter_ipv4_addresses
        netutils.iter_ipv4_addresses = lambda: []

        ip_addr, port = "<broadcast>", 23034
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client.bind(('', 0))
        client.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        client.sendto("QUERY".encode('UTF-8'), (ip_addr, port))

        client.settimeout(5)
        data, _ = client.recvfrom(1024)

        assert data.decode() == "{}"

        netutils.iter_ipv4_addresses = backup

    def test_get_message_server_address(self):
        ip_addr, port = "<broadcast>", 23034
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client.bind(('', 0))
        client.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        client.sendto("QUERY".encode('UTF-8'), (ip_addr, port))

        client.settimeout(5)
        data, _ = client.recvfrom(1024)

        obj = json.loads(data.decode())["host"]
        assert obj in [x["addr"] for x in netutils.iter_ipv4_addresses()]
