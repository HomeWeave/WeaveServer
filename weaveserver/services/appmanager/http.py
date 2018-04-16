import logging
import os

from bottle import Bottle, static_file


logger = logging.getLogger(__name__)


class HTTPServer(Bottle):
    def __init__(self, service, plugin_path):
        super().__init__()
        self.service = service

        self.static_path = os.path.join(os.path.dirname(__file__), "static")
        self.plugin_path = plugin_path

        self.route("/static/<path:path>")(self.handle_static)
        self.route("/")(self.handle_root)
        self.route("apps/<path:path>")(self.handle_apps)

        logger.info("Temp Dir for HTTP: %s", plugin_path)

    def handle_static(self, path):
        logger.info("Static: %s (within %s)", path, self.static_path)
        return static_file(path, root=self.static_path)

    def handle_root(self):
        return self.handle_static("/index.html")

    def handle_apps(self, path):
        return static_file(path, root=os.path.join(self.plugin_path))
