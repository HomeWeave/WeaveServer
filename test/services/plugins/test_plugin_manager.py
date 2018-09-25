import os
from tempfile import TemporaryDirectory
from unittest.mock import Mock

import pytest
from weavelib.exceptions import ObjectNotFound
from weavelib.messaging import WeaveConnection
from weavelib.rpc import RPCClient
from weavelib.services import BackgroundThreadServiceStart

import weaveserver.services.plugins.plugins
from weaveserver.services.core import CoreService
from weaveserver.services.simpledb import SimpleDatabaseService
from weaveserver.services.plugins import PluginService
from weaveserver.services.http import HTTPService
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
    "auth4": {
        "appid": "auth4",
        "package": "weaveserver.services.http",
        "type": "SYSTEM"
    },
}


class ThreadedDBService(BackgroundThreadServiceStart, SimpleDatabaseService):
    pass


class ThreadedPluginService(BackgroundThreadServiceStart, PluginService):
    pass


class ThreadedHTTPService(BackgroundThreadServiceStart, HTTPService):
    pass


class TestPluginService(object):
    @classmethod
    def setup_class(cls):
        cls.core_service = CoreService("auth1",
                                       {"apps": AUTH, "core_config": {}})
        cls.core_service.service_start()
        cls.core_service.wait_for_start(30)

        cls.conn = WeaveConnection.local()
        cls.conn.connect()

        cls.db_dir = TemporaryDirectory()
        db_config = {
            "core": {
                "DB_PATH": os.path.join(cls.db_dir.name, "DB")
            }
        }
        cls.db_service = ThreadedDBService("auth2", db_config)
        cls.db_service.service_start()
        cls.db_service.wait_for_start(30)

        cls.http_service = ThreadedHTTPService("auth4", {})
        cls.http_service.service_start()
        cls.http_service.wait_for_start(30)

        FakeGithubClass = Mock()
        fake_github = Mock()
        FakeGithubClass.return_value = fake_github
        org1 = Mock()
        repo1 = Mock()
        repo1.directory_contents.return_value = ["plugin.json"]
        repo1.clone_url = "clone-url-1"
        repo1.name = "repo1"
        repo1.description = "desc"
        repo2 = Mock()
        repo2.directory_contents.return_value = ["random-file"]
        repo2.clone_url = "clone-url-2"

        org1.repositories.return_value = [repo1, repo2]

        fake_github.organization.return_value = org1
        weaveserver.services.plugins.plugins.GitHub = FakeGithubClass
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
        cls.http_service.service_stop()
        cls.db_service.service_stop()
        cls.core_service.service_stop()

        cls.db_dir.cleanup()
        cls.temp_dir.cleanup()

    def test_available_plugins(self):
        rpc_client = RPCClient(self.conn, self.plugin_service.rpc.info_message,
                               "auth4")
        rpc_client.start()
        expected = {"clone-url-1"}
        available = rpc_client["list_available"](_block=True)
        available = {x["url"] for x in available}
        assert available == expected
        rpc_client.stop()

    def test_supported_plugins(self):
        rpc_client = RPCClient(self.conn, self.plugin_service.rpc.info_message,
                               "auth4")
        rpc_client.start()
        expected = ["git", "file"]
        assert rpc_client["supported_plugin_types"](_block=True) == expected
        rpc_client.stop()

    def test_install_plugin(self):
        rpc_client = RPCClient(self.conn, self.plugin_service.rpc.info_message,
                               "auth4")
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
        plugin_rpc = RPCClient(self.conn, info, "auth4")
        plugin_rpc.start()
        assert plugin_rpc["test"](_block=True) == "test"

        plugin_rpc.stop()

        # Deactivate
        assert rpc_client["deactivate"](plugin_id, _block=True)
        with pytest.raises(ObjectNotFound):
            self.plugin_service.rpc_client["rpc_info"](package, "test_plugin",
                                                       _block=True)

        rpc_client.stop()
