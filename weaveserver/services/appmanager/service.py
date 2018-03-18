import json
import logging
from threading import Event, RLock, Thread
from uuid import uuid4

from bottle import Bottle, abort, response
from jsonschema import Draft4Validator

from weavelib.messaging import Creator
from weavelib.rpc import RPCServer, ServerAPI, ArgParameter
from weavelib.services import BaseService, BackgroundProcessServiceStart


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


class ApplicationHTTP(Bottle):
    def __init__(self):
        super().__init__()
        self.views = {}
        self.view_lock = RLock()

        self.route("/views/<path>")(self.handle_view)

    def handle_view(self, path):
        with self.view_lock:
            obj = self.views.get(path)
        if not obj:
            abort(404, "Not found.")
        response.content_type = "application/json"
        return obj

    def register_view(self, obj):
        json_str = json.dumps(obj)
        unique_id = "app-http-view-" + str(uuid4())

        with self.view_lock:
            self.views[unique_id] = json_str

        return "/views/" + unique_id


class ApplicationRPC(object):
    APIS_SCHEMA = {
        "type": "object",
    }

    def __init__(self, service):
        self.service = service
        self.rpc = RootRPCServer("app_manager", "Application Manager", [
            ServerAPI("register_rpc", "Register new RPC", [
                ArgParameter("name", "Name of the RPC", str),
                ArgParameter("description", "Description of RPC", str),
                ArgParameter("apis", "Maps of all APIs", self.APIS_SCHEMA),
            ], self.register_rpc),
            ServerAPI("register_app_view", "Jasonette view to register.", [
                ArgParameter("object", "Regular(JSON) Object to register",
                             {"type": "object"})
            ], self.register_view)
        ], service)
        self.queue_creator = Creator(auth=service.auth_token)

        self.all_rpcs = {}

    def start(self):
        self.rpc.start()
        self.queue_creator.start()

    def stop(self):
        self.rpc.stop()
        self.queue_creator.close()

    def register_rpc(self, name, description, apis):
        caller_app_id = get_rpc_caller()["appid"]

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

        self.all_rpcs[base_queue] = {
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

    def register_view(self, obj):
        return self.service.http.register_view(obj)


class ApplicationService(BackgroundProcessServiceStart, BaseService):
    def __init__(self, token, config):
        super().__init__(token)
        self.http = ApplicationHTTP()
        self.rpc = ApplicationRPC(self)
        self.exited = Event()

    def before_service_start(self):
        """Needs to be overridden to prevent rpc_client connecting."""

    def on_service_start(self, *args, **kwargs):
        self.rpc.start()
        Thread(target=self.http.run, kwargs={"host": "", "port": 5000},
               daemon=True).start()
        self.notify_start()
        self.exited.wait()

    def on_service_stop(self):
        self.exited.set()
        self.rpc.stop()
