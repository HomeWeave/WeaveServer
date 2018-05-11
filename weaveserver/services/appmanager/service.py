import base64
import logging
import os
from collections import defaultdict
from tempfile import TemporaryDirectory
from threading import Event, Thread
from uuid import uuid4

from jsonschema import Draft4Validator

from weavelib.exceptions import ObjectNotFound
from weavelib.messaging import Creator
from weavelib.rpc import RPCServer, ServerAPI, ArgParameter, get_rpc_caller
from weavelib.services import BaseService, BackgroundProcessServiceStart

from .http import HTTPServer
from .application import RPCInfo, AppResource, Application


logger = logging.getLogger(__name__)


class RootRPCServer(RPCServer):
    MAX_RPC_WORKERS = 1  # Ensures single-thread to create all queues.

    def register_rpc(self):
        request_queue = "/_system/root_rpc/request"
        response_queue = "/_system/root_rpc/response"

        creator = Creator(auth=self.service.auth_token)
        creator.start()
        creator.create({
            "queue_name": request_queue,
            "request_schema": Draft4Validator.META_SCHEMA,
            "force_auth": True
        })

        creator.create({
            "queue_name": response_queue,
            "queue_type": "sessionized",
            "request_schema": {}
        })

        return dict(request_queue=request_queue, response_queue=response_queue)


class ApplicationRegistry(object):
    APIS_SCHEMA = {
        "type": "object",
    }

    def __init__(self, service, plugin_path):
        self.rpc = RootRPCServer("app_manager", "Application Manager", [
            ServerAPI("register_rpc", "Register new RPC", [
                ArgParameter("name", "Name of the RPC", str),
                ArgParameter("description", "Description of RPC", str),
                ArgParameter("apis", "Maps of all APIs", self.APIS_SCHEMA),
            ], self.register_rpc),
            ServerAPI("register_view", "Register resources to HTTP server", [
                ArgParameter("url", "URL to register to.", {"type": "string"}),
                ArgParameter("content", "Resource content", {"type": "string"}),
                ArgParameter("mimetype", "Resource MIME", {"type": "string"}),
            ], self.register_view),
            ServerAPI("register_app", "Register App", [], self.register_app),
            ServerAPI("rpc_info", "Get RPCInfo object.", [
                ArgParameter("package_name", "Package Name", str),
                ArgParameter("rpc_name", "RPC Name", str),
            ], self.rpc_info)
        ], service)
        self.queue_creator = Creator(auth=service.auth_token)
        self.plugin_path = plugin_path
        self.all_rpcs = defaultdict(dict)
        self.all_apps = {}

    def start(self):
        self.rpc.start()
        self.queue_creator.start()

    def stop(self):
        self.rpc.stop()
        self.queue_creator.close()

    def register_rpc(self, name, description, apis):
        caller_app = get_rpc_caller()
        caller_app_id = caller_app["appid"]

        base_queue = "/components/{}/rpcs/{}".format(caller_app_id,
                                                     str(uuid4()))
        request_queue = base_queue + "/request"
        response_queue = base_queue + "/response"

        get_schema = lambda x: ServerAPI.from_info(x).schema
        request_schema = {
            "type": "object",
            "properties": {
                "invocation": {
                    "anyOf": [get_schema(x) for x in apis.values()]
                }
            }
        }
        response_schema = {"type": "object"}

        self.queue_creator.create({
            "queue_name": request_queue,
            "request_schema": request_schema,
        })

        self.queue_creator.create({
            "queue_name": response_queue,
            "request_schema": response_schema
        })

        rpc_info = RPCInfo(name, description, apis, request_queue,
                           response_queue, request_schema, response_schema)
        self.all_rpcs[caller_app_id][name] = rpc_info.to_json()
        self.all_rpcs[caller_app_id][name]["app_id"] = caller_app_id

        self.all_apps[caller_app_id].register_rpc(rpc_info)

        return dict(request_queue=request_queue, response_queue=response_queue)

    def register_view(self, url, content, mimetype):
        caller_app = get_rpc_caller()
        caller_app_id = caller_app["appid"]

        decoded = base64.b64decode(content)
        path = os.path.join(self.plugin_path, caller_app_id)

        app_resource = AppResource.create(path, url, mimetype, decoded)
        if url == "_status-card.json":
            self.all_apps[caller_app_id].register_status_card(app_resource)
        else:
            # TODO: app_resource should not be accessible through static URL.
            self.all_apps[caller_app_id].register_app_resource(app_resource)

        return "/apps/" + caller_app_id + "/" + url.lstrip("/")

    def register_app(self):
        caller_app = get_rpc_caller()
        caller_app_id = caller_app["appid"]
        package = caller_app["package"]

        app = Application()
        app.package_name = package
        app.system_app = caller_app.get("type") == "SYSTEM"

        self.all_apps[caller_app_id] = app
        logger.info("Registered app: %s", package)

    def rpc_info(self, package_name, rpc_name):
        found_app = None
        for app in self.all_apps.values():
            if app.package_name == package_name:
                found_app = app
                break

        if not found_app:
            raise ObjectNotFound("Package not found: " + package_name)

        rpc_info = found_app.rpcs.get(rpc_name)
        if not rpc_info:
            raise ObjectNotFound("RPC not found: " + rpc_name)
        return rpc_info.to_json()


class ApplicationService(BackgroundProcessServiceStart, BaseService):
    def __init__(self, token, config):
        super().__init__(token)

        self.version = "latest"
        self.plugin_dir = TemporaryDirectory()
        self.plugins = {}
        self.registry = ApplicationRegistry(self, self.plugin_dir.name)
        self.http = HTTPServer(self, self.plugin_dir.name)
        self.exited = Event()

    def before_service_start(self):
        """Needs to be overridden to prevent rpc_client connecting."""

    def on_service_start(self, *args, **kwargs):
        self.registry.start()
        Thread(target=self.http.run, kwargs={"host": "", "port": 5000, "debug": True},
               daemon=True).start()
        self.notify_start()
        self.exited.wait()

    def on_service_stop(self):
        self.exited.set()
        self.plugin_dir.cleanup()
        self.registry.stop()
