from threading import Event, Thread

import app.core.netutils as netutils
from app.core.messaging import discover_message_server
from app.services.discovery import DiscoveryService


class TestDiscoverMessageServer(object):
    def test_no_discovery_server(self):
        assert discover_message_server() is None

    def test_discovery_server_bad_json(self):
        service = DiscoveryService(None)
        service.server.process = lambda x, y: "sdf;lghkd;flkh".encode("UTF-8")
        event = Event()
        service.notify_start = event.set
        Thread(target=service.on_service_start).start()
        event.wait()

        assert discover_message_server() is None
        service.on_service_stop()

    def test_discovery_server_unknown_json(self):
        service = DiscoveryService(None)
        service.server.process = lambda x, y: '{"vld": "json"}'.encode("UTF-8")
        event = Event()
        service.notify_start = event.set
        Thread(target=service.on_service_start).start()
        event.wait()

        assert discover_message_server() is None
        service.on_service_stop()

    def test_valid_discovery_server(self):
        service = DiscoveryService(None)
        event = Event()
        service.notify_start = event.set
        Thread(target=service.on_service_start).start()
        event.wait()

        ip_addresses = [x["addr"] for x in netutils.iter_ipv4_addresses()]
        try:
            assert discover_message_server()[0] in ip_addresses
        finally:
            service.on_service_stop()
