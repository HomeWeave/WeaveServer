from threading import Event, Thread

import app.core.netutils as netutils
from app.core.messaging import discover_message_server, Sender, Receiver
from app.core.messaging import SyncMessenger
from app.services.discovery import DiscoveryService
from app.services.discovery.service import DiscoveryServer
from app.services.messaging import MessageService


CONFIG = {
    "redis_config": {
        "USE_FAKE_REDIS": True
    },
    "queues": {
        "custom_queues": [
            {
                "queue_name": "dummy",
                "request_schema": {"type": "object"}
            }
        ]
    }
}


class TestDiscoverMessageServer(object):
    @classmethod
    def setup_class(cls):
        DiscoveryServer.ACTIVE_POLL_TIME = 1

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


class TestSyncMessenger(object):
    @classmethod
    def setup_class(cls):
        event = Event()
        cls.service = MessageService(CONFIG)
        cls.service.notify_start = lambda: event.set()
        cls.service_thread = Thread(target=cls.service.on_service_start)
        cls.service_thread.start()
        event.wait()

        cls.start_echo_receiver("dummy")

    @classmethod
    def teardown_class(cls):
        cls.service.on_service_stop()
        cls.service_thread.join()

    @classmethod
    def start_echo_receiver(cls, queue):
        sender = Sender(queue)
        sender.start()

        def reply(msg):
            sender.send(msg)

        receiver = Receiver(queue)
        receiver.on_message = reply
        receiver.start()

    def test_send_sync(self):
        obj = {"test": "test-messsage", "arr": [1, 2, 3]}

        sync = SyncMessenger("dummy")
        sync.start()

        assert obj == sync.send(obj)

        sync.stop()
