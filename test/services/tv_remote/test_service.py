import os

from roku import Roku

from app.core.messaging import Receiver
from app.core.servicemanager import ServiceManager
from app.services.tv_remote.service import RokuScanner, RokuTV


class TestRokuScanner(object):
    @classmethod
    def setup_class(cls):
        os.environ["USE_FAKE_REDIS"] = "TRUE"
        cls.service_manager = ServiceManager(None)
        cls.service_manager.start_services(["messaging"])

    @classmethod
    def teardown_class(cls):
        del os.environ["USE_FAKE_REDIS"]
        cls.service_manager.stop()

    def test_basic_discovery(self):
        roku1 = Roku("abc")
        scanner = RokuScanner("/devices", scan_interval=10)
        scanner.discover_devices = lambda: [roku1]
        scanner.get_device_id = lambda: "deviceid"
        scanner.start()

        receiver = Receiver("/devices")
        msg = receiver.receive()
        expected = {
            "deviceid": {
                "device_id": "deviceid",
                "device_command_queue": "devices/tv/command",
                "device_commands": RokuTV(None, None).read_commands()
            }
        }
        assert msg == expected
