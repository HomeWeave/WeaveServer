import logging
from threading import Event

from weavelib.rpc import RPCServer, ServerAPI, ArgParameter
from weavelib.services import BaseService, BackgroundProcessServiceStart

from .plugins import PluginManager


logger = logging.getLogger(__name__)


class PluginService(BackgroundProcessServiceStart, BaseService):
    def __init__(self, token, config):
        super().__init__(token)
        path = config["plugins"].get("PLUGIN_DIR")
        self.plugin_manager = PluginManager(path)
        self.rpc = RPCServer("object_store", "Object Store for all plugins.", [
            ServerAPI("activate", "Activate a plugin.", [
                ArgParameter("id", "ID of the plugin to activate", str),
            ], self.plugin_manager.activate),
            ServerAPI("deactivate", "Activate a plugin.", [
                ArgParameter("id", "ID of the plugin to deactivate", str),
            ], self.plugin_manager.deactivate),
            ServerAPI("list", "List all installed plugins", [],
                      self.plugin_manager.list_installed_plugins),
        ], self)
        self.shutdown = Event()

    def on_service_start(self, *args, **kwargs):
        super(PluginService, self).on_service_start(*args, **kwargs)
        self.plugin_manager.start()
        self.rpc.start()
        self.notify_start()
        self.shutdown.wait()

    def on_service_stop(self):
        self.rpc.stop()
        self.plugin_manager.stop()
        self.shutdown.set()
