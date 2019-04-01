from threading import Thread, Event

from weavelib.messaging import WeaveConnection
from weavelib.services import BaseService, BackgroundThreadServiceStart

from messaging.messaging.server import MessageServer
from messaging.discovery.service import DiscoveryServer
from messaging.messaging.appmgr import ApplicationRegistry


PORT = 11023


class CoreService(BackgroundThreadServiceStart, BaseService):
    def __init__(self, token):
        super(CoreService, self).__init__(token)
        self.message_server_started = Event()
        self.shutdown_event = Event()

        self.message_server = MessageServer(PORT, apps_auth,
                                            self.message_server_started.set)
        self.message_server_thread = Thread(target=self.message_server.run)
        self.discovery_server = DiscoveryServer(PORT)
        self.conn = WeaveConnection.local()
        self.registry = ApplicationRegistry(self.conn, self)

    def before_service_start(self):
        """Need to override to prevent rpc_client connecting."""

    def on_service_start(self, *args, **kwargs):
        self.message_server_thread.start()
        self.message_server_started.wait()
        self.conn.connect()
        self.registry.start()
        self.notify_start()
        self.shutdown_event.wait()

    def on_service_stop(self):
        self.registry.stop()
        self.conn.close()
        self.message_server.shutdown()
        self.message_server_thread.join()
        self.shutdown_event.set()
