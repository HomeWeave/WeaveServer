from threading import Event

from weavelib.rpc import RPCServer, ServerAPI
from weavelib.services import BasePlugin


class TestPluginService(BasePlugin):
    def __init__(self, *args, **kwargs):
        super(TestPluginService, self).__init__(*args, **kwargs)
        self.rpc = RPCServer("test_plugin", "", [
            ServerAPI("test", "", [], self.test)
        ], self, self.conn)
        self.exited = Event()

    def test(self):
        return "test"

    def on_service_start(self, *args, **kwargs):
        self.rpc.start()
        self.notify_start()
        self.exited.wait()

    def on_service_stop(self):
        self.exited.set()
        self.rpc.stop()
