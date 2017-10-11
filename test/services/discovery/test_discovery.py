import json
import socket
from threading import Event, Thread

import pytest

import app.core.netutils as netutils
from app.services.discovery import DiscoveryService


class TestDiscoveryService(object):
    @classmethod
    def setup_class(cls):
        cls.service = DiscoveryService(None)
        event = Event()
        cls.service.notify_start = event.set
        Thread(target=cls.service.on_service_start).start()
        event.wait()

    @classmethod
    def teardown_class(cls):
        cls.service.on_service_stop()

    def test_bad_query(self):
        ip_addr, port = "224.108.73.1", 23034
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client.sendto("BAD_QUERY".encode('UTF-8'), (ip_addr, port))

        client.settimeout(3)
        with pytest.raises(socket.timeout):
            client.recvfrom(1024)

    def test_no_machine_addresses(self):
        backup = netutils.iter_ipv4_addresses
        netutils.iter_ipv4_addresses = lambda: []

        ip_addr, port = "224.108.73.1", 23034
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client.sendto("QUERY".encode('UTF-8'), (ip_addr, port))

        client.settimeout(5)
        data, _ = client.recvfrom(1024)

        assert data.decode() == "{}"

        netutils.iter_ipv4_addresses = backup

    def test_get_message_server_address(self):
        ip_addr, port = "224.108.73.1", 23034
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client.sendto("QUERY".encode('UTF-8'), (ip_addr, port))

        client.settimeout(5)
        data, _ = client.recvfrom(1024)

        obj = json.loads(data.decode())["host"]
        assert obj in [x["addr"] for x in netutils.iter_ipv4_addresses()]