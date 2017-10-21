import os

from roku import Roku

from app.core.messaging import Receiver
from app.core.services import ServiceManager
from app.services.tv_remote.service import RokuScanner, RokuTV


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
        scanner = RokuScanner("/devices")
        scanner.discover_devices = lambda: [roku1]
        scanner.get_device_id = lambda x: "deviceid"
        scanner.start()

        receiver = Receiver("/devices")
        receiver.start()
        msg = receiver.receive().task
        expected = {
            "deviceid": {
                "device_id": "deviceid",
                "device_commands_queue": "/device/tv/command",
                "device_commands": RokuTV(None, None).read_commands()
            }
        }
        assert msg == expected

        receiver.stop()
        scanner.stop()

    def test_new_tv_discovery(self):
        roku1 = Roku("abc")
        roku2 = Roku("def")
        scanner = RokuScanner("/devices")
        scanner.discover_devices = lambda: [roku1]
        scanner.get_device_id = lambda x: x
        scanner.start()

        receiver = Receiver("/devices")
        receiver.start()
        msg = receiver.receive().task
        expected = {
            "abc": {
                "device_id": "abc",
                "device_commands_queue": "/device/tv/command",
                "device_commands": RokuTV(None, None).read_commands()
            }
        }
        assert msg == expected

        scanner.discover_devices = lambda: [roku1, roku2]
        scanner.scan()

        msg = receiver.receive().task
        expected["def"] = expected["abc"].copy()
        expected["def"]["device_id"] = "def"

        assert msg == expected

        receiver.stop()
        scanner.stop()
