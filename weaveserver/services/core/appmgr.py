import logging
from collections import defaultdict
from uuid import uuid4

from jsonschema import Draft4Validator

from weavelib.exceptions import ObjectNotFound
from weavelib.messaging import Creator
from weavelib.rpc import RPCServer, ServerAPI, ArgParameter, get_rpc_caller

from .application import RPCInfo, Application


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

    def __init__(self, service):
        self.rpc = RootRPCServer("app_manager", "Application Manager", [
            ServerAPI("register_rpc", "Register new RPC", [
                ArgParameter("name", "Name of the RPC", str),
                ArgParameter("description", "Description of RPC", str),
                ArgParameter("apis", "Maps of all APIs", self.APIS_SCHEMA),
            ], self.register_rpc),
            ServerAPI("register_app", "Register App", [], self.register_app),
            ServerAPI("rpc_info", "Get RPCInfo object.", [
                ArgParameter("package_name", "Package Name", str),
                ArgParameter("rpc_name", "RPC Name", str),
            ], self.rpc_info),
            ServerAPI("build_info", "Get HomeWeave version info.", [],
                      self.build_info),
        ], service)
        self.queue_creator = Creator(auth=service.auth_token)
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

        if caller_app.get("type") == "SYSTEM":
            base_queue = "/_system/{}"
        else:
            base_queue = "/components/{}/rpcs/{}".format(caller_app_id,
                                                         str(uuid4()))
        request_queue = base_queue + "/request"
        response_queue = base_queue + "/response"

        def get_schema(info):
            return ServerAPI.from_info(info).schema

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
            "queue_type": "sessionized",
            "request_schema": response_schema
        })

        rpc_info = RPCInfo(name, description, apis, request_queue,
                           response_queue, request_schema, response_schema)
        self.all_rpcs[caller_app_id][name] = rpc_info.to_json()
        self.all_rpcs[caller_app_id][name]["app_id"] = caller_app_id

        self.all_apps[caller_app_id].register_rpc(rpc_info)

        return dict(request_queue=request_queue, response_queue=response_queue)

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

    def build_info(self):
        return "latest"
