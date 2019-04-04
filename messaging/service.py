from threading import Thread, Event

from weavelib.services import BasePlugin, MessagingEnabled

from messaging.server import MessageServer
from messaging.discovery import DiscoveryServer


PORT = 11023


class CoreService(BasePlugin, MessagingEnabled):
    def __init__(self, **kwargs):
        super(CoreService, self).__init__(**kwargs)
        self.message_server_started = Event()
        self.shutdown_event = Event()

        apps_auth = {
            self.get_auth_token(): {
                "type": "SYSTEM",
            }
        }
        self.message_server = MessageServer(PORT, apps_auth,
                                            self.message_server_started.set)
        self.message_server_thread = Thread(target=self.message_server.run)
        self.discovery_server = DiscoveryServer(PORT)
        self.discovery_server_thread = Thread(target=self.discovery_server.run)

    def before_service_start(self):
        """Need to override to prevent rpc_client connecting."""

    def on_service_start(self, *args, **kwargs):
        self.message_server_thread.start()
        self.message_server_started.wait()
        self.discovery_server_thread.start()
        self.notify_start()
        self.shutdown_event.wait()

    def on_service_stop(self):
        self.message_server.shutdown()
        self.message_server_thread.join()
        self.shutdown_event.set()
