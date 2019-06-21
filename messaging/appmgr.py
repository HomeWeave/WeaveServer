import logging
from uuid import uuid4

from weavelib.exceptions import ObjectNotFound, AuthenticationFailed
from weavelib.rpc import RPCServer, ServerAPI, ArgParameter, get_rpc_caller


logger = logging.getLogger(__name__)
SYSTEM_REGISTRY_BASE_QUEUE = "/_system/registry"


def get_rpc_request_queue(base_queue):
    return base_queue.rstrip('/') + "/request"


def get_rpc_response_queue(base_queue):
    return base_queue.rstrip('/') + "/response"


def create_rpc_queues(base_queue, request_schema, response_schema, registry):
        request_queue = get_rpc_request_queue(base_queue)
        response_queue = get_rpc_response_queue(base_queue)

        registry.create_queue(request_queue, request_schema, {}, 'fifo',
                              force_auth=True)
        registry.create_queue(response_queue, response_schema, {},
                              'sessionized', force_auth=False)
        return dict(request_queue=request_queue, response_queue=response_queue)


class RPCInfo(object):
    def __init__(self, app_id, app_url, name, desc, apis, base_queue,
                 req_schema, res_schema):
        self.app_id = app_id
        self.app_url = app_url
        self.name = name
        self.description = desc
        self.apis = apis
        self.base_queue = base_queue
        self.request_schema = req_schema
        self.response_schema = res_schema

    @property
    def request_queue(self):
        return get_rpc_request_queue(self.base_queue)

    @property
    def response_queue(self):
        return get_rpc_response_queue(self.base_queue)

    def to_json(self):
        return {
            "app_id": self.app_id,
            "app_url": self.app_url,
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

    def __init__(self, name, desc, apis, service, channel_registry):
        super(RootRPCServer, self).__init__(name, desc, apis, service)
        self.channel_registry = channel_registry

    def register_rpc(self):
        return create_rpc_queues(SYSTEM_REGISTRY_BASE_QUEUE, {}, {},
                                 self.channel_registry)


class MessagingRPCHub(object):
    APIS_SCHEMA = {"type": "object"}

    def __init__(self, service, channel_registry, app_registry):
        self.rpc = RootRPCServer("app_manager", "Application Manager", [
            ServerAPI("register_rpc", "Register new RPC", [
                ArgParameter("name", "Name of the RPC", str),
                ArgParameter("description", "Description of RPC", str),
                ArgParameter("apis", "Maps of all APIs", self.APIS_SCHEMA),
            ], self.register_rpc),
            ServerAPI("register_plugin", "Register Plugin", [
                ArgParameter("app_id", "Plugin ID (within WeaveEnv)", str),
                ArgParameter("name", "Plugin Name", str),
                ArgParameter("url", "Plugin URL (GitHub)", str),
            ], self.register_plugin),
            ServerAPI("unregister_plugin", "Unregister Plugin", [
                ArgParameter("token", "Plugin Token", str)
            ], self.unregister_plugin),
            ServerAPI("rpc_info", "Get RPCInfo object.", [
                ArgParameter("app_url", "Plugin URL", str),
                ArgParameter("rpc_name", "RPC Name", str),
            ], self.rpc_info),
        ], service, channel_registry)
        self.channel_registry = channel_registry
        self.app_registry = app_registry
        self.rpc_registry = {}

    def start(self):
        # TODO: Fix request and response schema everywhere.
        rpc_info = RPCInfo("dummy_app_id",
                           "https://github.com/HomeWeave/WeaveServer.git",
                           self.rpc.name, self.rpc.description,
                           {x: y.info for x, y in self.rpc.apis.items()},
                           SYSTEM_REGISTRY_BASE_QUEUE, {}, {})
        self.rpc_registry["rpc-" + str(uuid4())] = rpc_info
        self.rpc.start()

    def stop(self):
        self.rpc.stop()

    def register_rpc(self, name, description, apis):
        caller_app = get_rpc_caller()
        app_id = caller_app["app_id"]
        app_url = caller_app["app_url"]
        rpc_id = "rpc-" + str(uuid4())
        base_queue = "/plugins/{}/rpcs/{}".format(caller_app["app_id"], rpc_id)
        request_schema = {
            "type": "object",
            "properties": {
                "invocation": {
                    "anyOf": [ServerAPI.from_info(x).schema
                              for x in apis.values()]
                }
            }
        }
        response_schema = {}
        res = create_rpc_queues(base_queue, request_schema, response_schema,
                                self.channel_registry)

        rpc_info = RPCInfo(app_id, app_url, name, description, apis, base_queue,
                           request_schema, response_schema)

        # Thread safe because MAX_RPC_WORKERS == 1.
        self.rpc_registry[rpc_id] = rpc_info
        logger.info("Registered RPC: %s(%s)", name, app_url)
        return res

    def register_plugin(self, app_id, name, url):
        caller_app = get_rpc_caller()
        if caller_app["app_type"] != "system":
            raise AuthenticationFailed("Only system apps can register plugins.")

        return self.app_registry.register_plugin(app_id, name, url)

    def unregister_plugin(self, token):
        caller_app = get_rpc_caller()
        if caller_app.get("type") != "system":
            raise AuthenticationFailed("Only system apps can stop plugins.")

        self.app_registry.unregister_plugin(token)
        return True

    def rpc_info(self, url, rpc_name):
        for rpc_info in self.rpc_registry.values():
            if rpc_info.app_url == url and rpc_info.name == rpc_name:
                return rpc_info.to_json()
        raise ObjectNotFound("RPC not found: " + rpc_name)
