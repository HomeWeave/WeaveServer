import logging
from threading import Event

from weavelib.db import AppDBConnection
from weavelib.rpc import RPCServer, ServerAPI, ArgParameter
from weavelib.services import BaseService, BackgroundProcessServiceStart

from .plugins import PluginManager


logger = logging.getLogger(__name__)


class PluginService(BackgroundProcessServiceStart, BaseService):
    def __init__(self, token, config):
        super().__init__(token)
        plugin_path = config["plugins"].get("PLUGIN_DIR")
        venv_path = config["plugins"].get("VENV_DIR")
        self.db = AppDBConnection(self)
        self.plugin_manager = PluginManager(plugin_path, venv_path, self.db)
        self.rpc = RPCServer("plugins", "External Plugins Manager.", [
            ServerAPI("activate", "Activate a plugin.", [
                ArgParameter("id", "ID of the plugin to activate", str),
            ], self.plugin_manager.activate),
            ServerAPI("deactivate", "Activate a plugin.", [
                ArgParameter("id", "ID of the plugin to deactivate", str),
            ], self.plugin_manager.deactivate),
            ServerAPI("list", "List all installed plugins", [],
                      self.plugin_manager.list_installed_plugins),
            ServerAPI("list_available", "List all available plugins.", [],
                      self.plugin_manager.list_available_plugins)
        ], self)
        self.shutdown = Event()

    def on_service_start(self, *args, **kwargs):
        super(PluginService, self).on_service_start(*args, **kwargs)
        self.db.start()
        self.plugin_manager.start()
        self.rpc.start()
        self.notify_start()
        self.shutdown.wait()

    def on_service_stop(self):
        self.rpc.stop()
        self.plugin_manager.stop()
        self.db.stop()
        self.shutdown.set()
