from threading import Thread, Event
from uuid import uuid4

from weavelib.messaging import WeaveConnection
from weavelib.services import BasePlugin, MessagingEnabled

from messaging.server import MessageServer
from messaging.discovery import DiscoveryServer
from messaging.application_registry import ApplicationRegistry
from messaging.queue_manager import ChannelRegistry
from messaging.appmgr import MessagingRPCHub


PORT = 11023


class CoreService(BasePlugin, MessagingEnabled):
    def __init__(self, **kwargs):
        messaging_token = "app-token-" + str(uuid4())
        weave_env_token = kwargs.pop('auth_token')
        conn = WeaveConnection.local()

        kwargs['auth_token'] = messaging_token
        kwargs['conn'] = conn

        super(CoreService, self).__init__(**kwargs)

        self.message_server_started = Event()
        self.shutdown_event = Event()

        app_registry = ApplicationRegistry([
            ("WeaveEnv", "http://github.com/HomeWeave/WeaveEnv.git",
             "app-id-weave-env", weave_env_token),
            ("MessagingServer", "http://github.com/HomeWeave/WeaveServer.git",
             "app-id-messaging", messaging_token),
        ])
        channel_registry = ChannelRegistry()

        self.message_server = MessageServer(PORT, app_registry,
                                            channel_registry,
                                            self.message_server_started.set)
        self.message_server_thread = Thread(target=self.message_server.run)
        self.discovery_server = DiscoveryServer(PORT)
        self.discovery_server_thread = Thread(target=self.discovery_server.run)
        self.rpc_hub = MessagingRPCHub(self, channel_registry, app_registry)

    def before_service_start(self):
        """Need to override to prevent rpc_client connecting."""

    def on_service_start(self, *args, **kwargs):
        self.message_server_thread.start()
        self.message_server_started.wait()
        self.discovery_server_thread.start()
        self.get_connection().connect()
        self.rpc_hub.start()
        self.notify_start()
        self.shutdown_event.wait()

    def on_service_stop(self):
        self.message_server.shutdown()
        self.message_server_thread.join()
        self.shutdown_event.set()
