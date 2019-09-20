from threading import Thread, Event

import pytest

from weavelib.exceptions import Unauthorized, AuthenticationFailed
from weavelib.messaging import WeaveConnection, Sender, Receiver
from weavelib.rpc import find_rpc, RPCClient, RPCServer, ServerAPI, ArgParameter

from messaging.application_registry import ApplicationRegistry
from messaging.appmgr import MessagingRPCHub
from messaging.queue_manager import ChannelRegistry
from messaging.server import MessageServer
from messaging.service import DummyMessagingService
from messaging.synonyms import SynonymRegistry


TEST_APP_TOKEN = "test-app"
MESSAGING_APP_TOKEN = "app-token"
PORT = 11023
MESSAGING_SERVER_URL = "https://github.com/HomeWeave/WeaveServer.git"
TEST_URL = "test-url"


class TestMessagingRPCHub(object):
    def setup_method(self):
        self.dummy_service = DummyMessagingService(MESSAGING_APP_TOKEN,
                                                   WeaveConnection.local())
        message_server_started = Event()
        app_registry = ApplicationRegistry([
            ("Test", TEST_URL, TEST_APP_TOKEN),
            ("MessagingServer", MESSAGING_SERVER_URL, MESSAGING_APP_TOKEN),
        ])
        channel_registry = ChannelRegistry(app_registry)

        synonym_registry = SynonymRegistry()
        self.message_server = MessageServer(PORT, app_registry,
                                            channel_registry, synonym_registry,
                                            message_server_started.set)
        self.message_server_thread = Thread(target=self.message_server.run)
        rpc_hub = MessagingRPCHub(self.dummy_service, channel_registry,
                                  app_registry, synonym_registry)

        self.message_server_thread.start()
        message_server_started.wait()
        self.dummy_service.start()
        rpc_hub.start()

        self.weave_service = DummyMessagingService(TEST_APP_TOKEN,
                                                   WeaveConnection.local())
        self.weave_service.start()

        self.appmgr_rpc_info = find_rpc(self.weave_service,
                                        MESSAGING_SERVER_URL, "app_manager")

    def teardown_method(self):
        self.dummy_service.get_connection().close()
        self.weave_service.get_connection().close()
        self.message_server.shutdown()
        self.message_server_thread.join()

    def test_register_unregister_plugin(self):
        conn = WeaveConnection.local()
        conn.connect()
        client = RPCClient(conn, self.appmgr_rpc_info, TEST_APP_TOKEN)
        client.start()
        token = client["register_plugin"]("name", "url1", _block=True)
        assert token

        assert client["unregister_plugin"](token, _block=True)

        client.stop()
        conn.close()

    def test_register_as_non_system_app(self):
        conn = WeaveConnection.local()
        conn.connect()
        client = RPCClient(conn, self.appmgr_rpc_info, TEST_APP_TOKEN)
        client.start()
        token = client["register_plugin"]("name", "url1", _block=True)
        plugin_client = RPCClient(conn, self.appmgr_rpc_info, token)
        plugin_client.start()

        with pytest.raises(AuthenticationFailed):
            plugin_client["register_plugin"]("a", "b", _block=True)

        plugin_client.stop()
        client.stop()
        conn.close()

    def test_register_rpc_with_whitelists(self):
        conn = WeaveConnection.local()
        conn.connect()
        client = RPCClient(conn, self.appmgr_rpc_info, TEST_APP_TOKEN)
        client.start()

        data = {
            "1": {
                "name": "name1",
                "url": "url1",
                "rpc_name": "rpc1",
                "allowed_requestors": []
            },
            "2": {
                "name": "name2",
                "url": "url2",
                "rpc_name": "rpc2",
                "allowed_requestors": ["url1"]
            },
            "3": {
                "name": "name3",
                "url": "url3",
                "rpc_name": "rpc3",
                "allowed_requestors": ["diff-url"]
            },
        }

        for info in data.values():
            info["token"] = client["register_plugin"](info["name"], info["url"],
                                                      _block=True)

            service = DummyMessagingService(info["token"], conn)
            info["server"] = RPCServer(info["rpc_name"], "desc", [
                                         ServerAPI("name", "desc", [
                                           ArgParameter("param", "desc", str),
                                         ], lambda x: x),
                                       ],
                                       service, info["allowed_requestors"])
            info["server"].start()

            info["rpc_info"] = find_rpc(service, info["url"], info["rpc_name"])

        allowed_requestors = [
            ("1", "2"),
            ("1", "1"),
            ("2", "1"),
            ("3", "1"),
        ]

        disallowed_requestors = [
            ("1", "3"),
            ("2", "2"),
            ("2", "3"),
            ("3", "2"),
            ("3", "3")
        ]

        for source, target in allowed_requestors:
            plugin_client = RPCClient(conn, data[target]["rpc_info"],
                                      data[source]["token"])
            plugin_client.start()
            assert plugin_client["name"]("x", _block=True) == "x"
            plugin_client.stop()

        for source, target in disallowed_requestors:
            plugin_client = RPCClient(conn, data[target]["rpc_info"],
                                      data[source]["token"])
            plugin_client.start()
            with pytest.raises(Unauthorized):
                plugin_client["name"]("x", _block=True)
            plugin_client.stop()

        for info in data.values():
            info["server"].stop()

        client.stop()
        conn.close()

    def test_register_queue(self):
        conn = WeaveConnection.local()
        conn.connect()
        client = RPCClient(conn, self.appmgr_rpc_info, TEST_APP_TOKEN)
        client.start()

        res = client["register_queue"]("test_queue/", "fifo", {"type": "string"},
                                       [MESSAGING_SERVER_URL], [TEST_URL],
                                       _block=True)
        assert res == "/channels/{}/test_queue".format(TEST_URL)

        sender_no_auth = Sender(conn, res, auth=TEST_APP_TOKEN)
        sender_no_auth.start()
        with pytest.raises(Unauthorized):
            sender_no_auth.send("test")

        sender_auth = Sender(conn, res, auth=MESSAGING_APP_TOKEN)
        sender_auth.send("test")

        receiver_no_auth = Receiver(conn, res, auth=MESSAGING_APP_TOKEN)
        with pytest.raises(Unauthorized):
            receiver_no_auth.receive()

        receiver_auth = Receiver(conn, res, auth=TEST_APP_TOKEN)
        assert "test" == receiver_auth.receive().task

        client.stop()

