import base64
import logging
import os
from collections import defaultdict
from tempfile import TemporaryDirectory
from threading import Event, Thread
from uuid import uuid4

from jsonschema import Draft4Validator

from weavelib.messaging import Creator, QueueAlreadyExists
from weavelib.rpc import RPCServer, ServerAPI, ArgParameter, get_rpc_caller
from weavelib.services import BaseService, BackgroundProcessServiceStart

from .http import HTTPServer


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


class ApplicationRPC(object):
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
            ], self.register_view)
        ], service)
        self.queue_creator = Creator(auth=service.auth_token)
        self.plugin_path = plugin_path
        self.all_rpcs = defaultdict(dict)

    def start(self):
        self.rpc.start()
        self.queue_creator.start()

    def stop(self):
        self.rpc.stop()
        self.queue_creator.close()

    def register_rpc(self, name, description, apis):
        caller_app_id = get_rpc_caller()["appid"]

        if self.all_rpcs[caller_app_id][name]:
            raise QueueAlreadyExists(name)

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

        self.all_rpcs[caller_app_id][name] = {
            "app_id": caller_app_id,
            "name": name,
            "description": description,
            "apis": apis,
            "request_queue": request_queue,
            "response_queue": response_queue,
            "request_schema": request_schema,
            "response_schema": response_schema
        }

        return dict(request_queue=request_queue, response_queue=response_queue)

    def register_view(self, url, content, mimetype):
        decoded = base64.b64decode(content)
        app = get_rpc_caller()
        path = os.path.join(self.plugin_path, app["appid"])
        try:
            os.makedirs(path)
        except:
            pass
        path = os.path.join(path, url.lstrip("/"))
        with open(path, "wb") as out:
            out.write(decoded)
        return "/apps/" + app["appid"] + "/" + url.lstrip("/")


class ApplicationService(BackgroundProcessServiceStart, BaseService):
    def __init__(self, token, config):
        super().__init__(token)

        self.plugin_dir = TemporaryDirectory()
        self.rpc = ApplicationRPC(self, self.plugin_dir.name)
        self.http = HTTPServer(self, self.plugin_dir.name)
        self.exited = Event()

    def before_service_start(self):
        """Needs to be overridden to prevent rpc_client connecting."""

    def on_service_start(self, *args, **kwargs):
        self.rpc.start()
        Thread(target=self.http.run, kwargs={"host": "", "port": 5000, "debug": True},
               daemon=True).start()
        self.notify_start()
        self.exited.wait()

    def on_service_stop(self):
        self.exited.set()
        self.plugin_dir.cleanup()
        self.rpc.stop()
