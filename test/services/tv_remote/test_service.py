import os
from threading import Event

import pytest
from roku import Roku

from app.core.messaging import Receiver, Sender, SchemaValidationFailed
from app.core.services import ServiceManager
from app.services.tv_remote.service import RokuScanner, RokuTV, TVRemoteService


class TestRokuScanner(object):
    def setup_method(self):
        os.environ["USE_FAKE_REDIS"] = "TRUE"
        self.service_manager = ServiceManager(None)
        self.service_manager.start_services(["messaging"])

    def teardown_method(self):
        del os.environ["USE_FAKE_REDIS"]
        self.service_manager.stop()

    def test_basic_discovery(self):
        roku1 = Roku("abc")
        service = TVRemoteService(None)
        service.scanner.discover_devices = lambda: [roku1]
        service.scanner.get_device_id = lambda x: "deviceid"
        service.on_service_start()

        receiver = Receiver("/services/tv_remote/capabilities")
        receiver.start()
        msg = next(iter(receiver.receive().task.values()))
        assert set(msg.keys()) == {"description", "id", "name", "params",
                                   "queue"}

        receiver.stop()
        service.on_service_stop()

    def test_new_tv_discovery(self):
        roku1 = Roku("abc")
        roku2 = Roku("def")
        service = TVRemoteService(None)
        service.scanner.discover_devices = lambda: [roku1]
        service.scanner.get_device_id = lambda x: x
        service.on_service_start()

        receiver = Receiver("/services/tv_remote/capabilities")
        receiver.start()
        msg = next(iter(receiver.receive().task.values()))
        assert set(msg.keys()) == {"description", "id", "name", "params",
                                   "queue"}

        service.scanner.discover_devices = lambda: [roku1, roku2]

        msg = receiver.receive().task
        assert len(msg) == 2

        receiver.stop()
        service.on_service_stop()

    def test_send_command(self):
        called_with_url = None
        called = Event()

        def patched(obj, url):
            nonlocal called_with_url
            called_with_url = url
            called.set()

        Roku._post = patched
        roku1 = Roku("abc")
        service = TVRemoteService(None)
        service.scanner.discover_devices = lambda: [roku1]
        service.scanner.get_device_id = lambda x: "deviceid"
        service.on_service_start()

        receiver = Receiver("/services/tv_remote/capabilities")
        receiver.start()
        msg = next(iter(receiver.receive().task.values()))
        assert set(msg.keys()) == {"description", "id", "name", "params",
                                   "queue"}

        sender = Sender(msg["queue"])
        sender.start()
        with pytest.raises(SchemaValidationFailed):
            sender.send({"command_id": "non-existant", "command_args": ""})

        sender.send({"command_id": "back", "command_args": ""})

        called.wait()
        assert called_with_url == '/keypress/Back'

        receiver.stop()
        service.on_service_stop()
