import logging
from collections import defaultdict
from uuid import uuid4

from jsonschema import Draft4Validator

from weavelib.exceptions import ObjectNotFound, AuthenticationFailed
from weavelib.rpc import RPCServer, ServerAPI, ArgParameter, get_rpc_caller

from .application import RPCInfo, Application


logger = logging.getLogger(__name__)


def create_rpc_queues(base_queue, request_schema, response_schema, registry):
        request_queue = base_queue.rstrip('/') + "/request"
        response_queue = base_queue.rstrip('/') + "/response"

        registry.create_queue(request_queue, request_schema, {}, 'fifo',
                              force_auth=True)
        registry.create_queue(response_queue, response_schema, {},
                              'sessionized', force_auth=False)
        return dict(request_queue=request_queue, response_queue=response_queue)


class RPCInfo(object):
    def __init__(self, name, desc, apis, req_queue, res_queue, req_schema,
                 res_schema):
        self.name = name
        self.description = desc
        self.apis = apis
        self.request_queue = req_queue
        self.response_queue = res_queue
        self.request_schema = req_schema
        self.response_schema = res_schema

    def to_json(self):
        return {
            "name": self.name,
            "description": self.description,
            "apis": self.apis,
            "request_queue": self.request_queue,
            "response_queue": self.response_queue,
            "request_schema": self.request_schema,
            "response_schema": self.response_schema
        }


class RootRPCServer(RPCServer):
    MAX_RPC_WORKERS = 1  # Ensures single-thread to create all queues.

    def __init__(self, name, desc, apis, service, conn, channel_registry):
        super(RootRPCServer, self).__init__(name, desc, apis, service, conn)
        self.channel_registry = channel_registry

    def register_rpc(self):
        return create_rpc_queues("/_system/registry", {}, {},
                                 self.channel_registry)


class MessagingRPCHub(object):
    APIS_SCHEMA = {
        "type": "object",
    }
    PLUGIN_INFO_SCHEMA = {
        "type": "object"
    }

    def __init__(self, conn, channel_registry, app_registry):
        self.rpc = RootRPCServer("app_manager", "Application Manager", [
            ServerAPI("register_rpc", "Register new RPC", [
                ArgParameter("name", "Name of the RPC", str),
                ArgParameter("description", "Description of RPC", str),
                ArgParameter("apis", "Maps of all APIs", self.APIS_SCHEMA),
            ], self.register_rpc),
            ServerAPI("register_plugin", "Register Plugin", [
                ArgParameter("plugin_info", "Plugin Information",
                             self.PLUGIN_INFO_SCHEMA)
            ], self.register_plugin),
            ServerAPI("unregister_plugin", "Unregister Plugin", [
                ArgParameter("token", "Plugin Token", str)
            ], self.unregister_plugin),
            ServerAPI("rpc_info", "Get RPCInfo object.", [
                ArgParameter("package_name", "Package Name", str),
                ArgParameter("rpc_name", "RPC Name", str),
            ], self.rpc_info),
        ], service, conn)
        self.channel_registry = channel_registry
        self.app_registry = app_registry

    def start(self):
        self.rpc.start()

    def stop(self):
        self.rpc.stop()

    def register_rpc(self, name, description, apis):
        caller_app = get_rpc_caller()
        caller_app_id = caller_app["appid"]
        base_queue = "/components/{}/rpcs/{}".format(caller_app_id,
                                                     str(uuid4()))
        request_schema = {
            "type": "object",
            "properties": {
                "invocation": {
                    "anyOf": [ServerAPI.from_info(x).schema
                              for x in apis.values()]
                }
            }
        }
        response_schema = {"type": "object"}
        res = create_rpc_queues(base_queue, request_schema, response_schema,
                                self.channel_registry)

        rpc_info = RPCInfo(name, description, apis, request_queue,
                           response_queue, request_schema, response_schema)

        self.all_apps[caller_app_id].register_rpc(rpc_info)

        return dict(request_queue=request_queue, response_queue=response_queue)

    def register_plugin(self, name, url):
        caller_app = get_rpc_caller()
        if caller_app["app_type"] != "SYSTEM":
            raise AuthenticationFailed("Only system apps can register plugins.")

        self.app_registry.register_application()

        return token

    def unregister_plugin(self, token):
        caller_app = get_rpc_caller()
        if caller_app.get("type") != "SYSTEM":
            raise ObjectNotFound("No such RPC.")

        # This works because token == plugin["appid"].
        self.all_apps.pop(token, None)
        # TODO: Remove RPC calls,m close queues etc.

        self.app_registry.unregister_application(token)

        return True

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
