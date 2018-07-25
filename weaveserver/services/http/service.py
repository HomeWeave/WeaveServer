import base64
import logging
import os
from collections import defaultdict
from tempfile import TemporaryDirectory
from threading import Event, Thread

from weavelib.rpc import RPCServer, ServerAPI, ArgParameter, get_rpc_caller
from weavelib.services import BaseService, BackgroundProcessServiceStart

from .http import HTTPServer


logger = logging.getLogger(__name__)


class AppResource(object):
    def __init__(self, app_resource_dir, path, mime):
        self.app_resource_dir = app_resource_dir
        self.path = path
        self.mime = mime

    def read(self):
        with open(os.path.join(self.app_resource_dir, self.path), 'rb') as inp:
            return inp.read()

    @staticmethod
    def create(app_resource_dir, path, mime, content):
        path = path.lstrip("/")
        full_path = os.path.join(app_resource_dir, path)
        try:
            os.makedirs(os.path.dirname(full_path))
        except:
            pass
        with open(full_path, "wb") as out:
            out.write(content)

        return AppResource(app_resource_dir, path, mime)


class HTTPResourceRegistry(object):
    def __init__(self, service, plugin_path):
        self.rpc = RPCServer("http", "Manage HTTP server.", [
            ServerAPI("register_view", "Register resources to HTTP server", [
                ArgParameter("url", "URL to register to.", {"type": "string"}),
                ArgParameter("content", "Resource content", {"type": "string"}),
                ArgParameter("mimetype", "Resource MIME", {"type": "string"}),
            ], self.register_view),
        ], service)
        self.plugin_path = plugin_path
        self.all_resources = defaultdict(dict)

    def start(self):
        self.rpc.start()

    def stop(self):
        self.rpc.stop()

    def register_view(self, url, content, mimetype):
        logger.info("Registering resource: %s", url)
        caller_app = get_rpc_caller()
        package = caller_app["package"]

        decoded = base64.b64decode(content)
        path = os.path.join(self.plugin_path, package)

        app_resource = AppResource.create(path, url, mimetype, decoded)

        final_url = "/apps/" + package + "/" + url.lstrip("/")
        self.all_resources[package][final_url] = app_resource

        return final_url


class HTTPService(BackgroundProcessServiceStart, BaseService):
    def __init__(self, token, config):
        super().__init__(token)
        self.plugin_dir = TemporaryDirectory()
        self.http_registry = HTTPResourceRegistry(self, self.plugin_dir.name)
        self.http = HTTPServer(self, self.plugin_dir.name)
        self.exited = Event()

    def on_service_start(self, *args, **kwargs):
        self.http_registry.start()
        Thread(target=self.http.run,
               kwargs={"host": "", "port": 5000, "debug": True},
               daemon=True).start()
        self.notify_start()
        self.exited.wait()

    def on_service_stop(self):
        self.exited.set()
        self.plugin_dir.cleanup()
        self.http_registry.stop()
