from threading import Thread, Event

from weavelib.services import BaseService, BackgroundThreadServiceStart

from .server import MessageServer
from .appmgr import ApplicationRegistry


PORT = 11023


class CoreService(BackgroundThreadServiceStart, BaseService):
    def __init__(self, token, config):
        super(CoreService, self).__init__(token)
        config = config["core_config"]

        self.apps_auth = {
            token: {"type": "SYSTEM", "appid": token}
        }
        self.message_server = MessageServer(self, config.get("PORT") or PORT,
                                            self.apps_auth,
                                            self.message_server_started)
        self.message_server_thread = Thread(target=self.message_server.run)
        self.registry = ApplicationRegistry(self)
        self.shutdown_event = Event()

    def message_server_started(self):
        self.registry.start()

    def before_service_start(self):
        """Need to override to prevent rpc_client connecting."""

    def on_service_start(self, *args, **kwargs):
        self.message_server_thread.start()
        # self.registry will be started when message_server_started is called.

        self.shutdown_event.wait()

    def on_service_stop(self):
        self.registry.stop()
        self.message_server.shutdown()
        self.message_server_thread.join()
        self.shutdown_event.set()
