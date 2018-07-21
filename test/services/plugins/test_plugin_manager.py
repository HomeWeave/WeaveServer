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
        "package": "weaveserver.services.plugins",
        "type": "SYSTEM"
    },
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

        cls.temp_dir = TemporaryDirectory()
        plugin_dir = os.path.join(cls.temp_dir.name, 'plugins')
        venv_dir = os.path.join(cls.temp_dir.name, 'venv')
        os.makedirs(plugin_dir)
        os.makedirs(venv_dir)
        plugin_config = {
            "plugins": {
                "PLUGIN_DIR": plugin_dir,
                "VENV_DIR": venv_dir
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
        cls.temp_dir.cleanup()

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
        rpc_client.stop()

    def test_supported_plugins(self):
        rpc_client = RPCClient(self.plugin_service.rpc.info_message, "auth4")
        rpc_client.start()
        expected = ["git", "file"]
        assert rpc_client["supported_plugin_types"](_block=True) == expected
        rpc_client.stop()

    def test_install_plugin(self):
        rpc_client = RPCClient(self.plugin_service.rpc.info_message, "auth4")
        rpc_client.start()

        path = os.path.join(os.path.dirname(__file__), 'test_dir/plugin1')
        plugin_id = rpc_client["install_plugin"]("file", path, _block=True)

        assert plugin_id

        assert rpc_client["activate"](plugin_id, _block=True)

        # Send a test RPC.
        package = "testplugin.TestPluginService"
        info = self.plugin_service.rpc_client["rpc_info"](package,
                                                          "test_plugin",
                                                          _block=True)
        plugin_rpc = RPCClient(info, "auth4")
        plugin_rpc.start()
        assert plugin_rpc["test"](_block=True) == "test"

        plugin_rpc.stop()
        rpc_client.stop()
