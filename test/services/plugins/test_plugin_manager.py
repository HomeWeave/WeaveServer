import os
import time
from tempfile import TemporaryDirectory

from weavelib.messaging import Receiver
from weavelib.rpc import RPCClient
from weavelib.services import BackgroundThreadServiceStart

from weaveserver.services.core import CoreService
from weaveserver.services.simpledb import SimpleDatabaseService
from weaveserver.services.plugins import PluginService
from weaveserver.core.logger import configure_logging


configure_logging()

AUTH = {
    "auth1": {
        "type": "SYSTEM",
        "package": "core",
        "appid": "auth1"
    },
    "auth2": {
        "appid": "auth2",
        "type": "SYSTEM",
        "package": "weaveserver.services.simpledb"
    },
    "auth3": {
        "appid": "auth3",
        "package": "plugin",
        "type": "SYSTEM"
    },
    "auth4": {
        "appid": "auth4",
        "package": "test",
    }
}


class ThreadedDBService(BackgroundThreadServiceStart, SimpleDatabaseService):
    pass


class ThreadedPluginService(BackgroundThreadServiceStart, PluginService):
    pass


class TestPluginService(object):
    @classmethod
    def setup_class(cls):
        cls.core_service = CoreService("auth1",
                                       {"apps": AUTH, "core_config": {}})
        cls.core_service.service_start()
        cls.core_service.wait_for_start(30)

        # cls.core_service.message_server.register_application(AUTH["auth2"])
        # cls.core_service.message_server.register_application(AUTH["auth3"])

        # Wait till it starts.
        receiver = Receiver("/_system/root_rpc/request")
        while True:
            try:
                receiver.start()
                break
            except IOError:
                time.sleep(1)

        cls.db_dir = TemporaryDirectory()
        db_config = {
            "core": {
                "DB_PATH": os.path.join(cls.db_dir.name, "DB")
            }
        }
        cls.db_service = ThreadedDBService("auth2", db_config)
        cls.db_service.service_start()
        cls.db_service.wait_for_start(30)

        cls.venv_dir = TemporaryDirectory()
        plugin_config = {
            "plugins": {
                "PLUGIN_DIR": os.path.join(os.path.dirname(__file__),
                                           'test_dir'),
                "VENV_DIR": cls.venv_dir.name,
            }
        }
        cls.plugin_service = ThreadedPluginService("auth3", plugin_config)
        cls.plugin_service.service_start()
        cls.plugin_service.wait_for_start(30)

    @classmethod
    def teardown_class(cls):
        cls.plugin_service.service_stop()
        cls.db_service.service_stop()
        cls.core_service.service_stop()

        cls.db_dir.cleanup()

    def test_list_installed_plugins(self):
        rpc_client = RPCClient(self.plugin_service.rpc.info_message, "auth4")
        rpc_client.start()
        assert rpc_client["list"](_block=True) == []

    def test_available_plugins(self):
        rpc_client = RPCClient(self.plugin_service.rpc.info_message, "auth4")
        rpc_client.start()
        expected = [
            {
                "url": "https://github.com/HomeWeave/PhilipsHue.git",
                "description": None,
                "enabled": False
            }
        ]
        assert rpc_client["list_available"](_block=True) == expected
