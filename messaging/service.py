from threading import Thread, Event
from uuid import uuid4

from weavelib.messaging import WeaveConnection
from weavelib.services import BackgroundProcessServiceStart, BaseService
from weavelib.services import MessagingEnabled

from messaging.server import MessageServer
from messaging.discovery import DiscoveryServer
from messaging.application_registry import ApplicationRegistry
from messaging.queue_manager import ChannelRegistry
from messaging.appmgr import MessagingRPCHub


PORT = 11023


class DummyMessagingService(MessagingEnabled):
    def __init__(self, auth_token, conn):
        super(DummyMessagingService, self).__init__(auth_token=auth_token,
                                                    conn=conn)

    def start(self):
        self.get_connection().connect()


class CoreService(BackgroundProcessServiceStart, BaseService):
    def __init__(self, **kwargs):
        super(CoreService, self).__init__(**kwargs)

        messaging_token = "app-token-" + str(uuid4())
        weave_env_token = kwargs.pop('auth_token')

        self.dummy_service = DummyMessagingService(messaging_token,
                                                   WeaveConnection.local())
        self.message_server_started = Event()
        self.shutdown_event = Event()
        app_registry = ApplicationRegistry([
            ("WeaveEnv", "https://github.com/HomeWeave/WeaveEnv.git",
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
        self.rpc_hub = MessagingRPCHub(self.dummy_service, channel_registry,
                                       app_registry)

    def before_service_start(self):
        """Need to override to prevent rpc_client connecting."""

    def on_service_start(self, *args, **kwargs):
        self.message_server_thread.start()
        self.message_server_started.wait()
        self.discovery_server_thread.start()
        self.dummy_service.start()
        self.rpc_hub.start()
        self.notify_start()
        self.shutdown_event.wait()

    def on_service_stop(self):
        self.dummy_service.get_connection().close()
        self.discovery_server.stop()
        self.discovery_server_thread.join()
        self.message_server.shutdown()
        self.message_server_thread.join()
        self.shutdown_event.set()
