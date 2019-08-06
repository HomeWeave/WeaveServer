import logging
from uuid import uuid4

from weavelib.exceptions import ObjectNotFound, AuthenticationFailed
from weavelib.exceptions import Unauthorized, ObjectAlreadyExists
from weavelib.rpc import RPCServer, ServerAPI, ArgParameter, get_rpc_caller

from messaging.authorizers import WhitelistAuthorizer, AllowAllAuthorizer


logger = logging.getLogger(__name__)
SYSTEM_REGISTRY_BASE_QUEUE = "/_system/registry"
MESSAGING_SERVER_URL = "https://github.com/HomeWeave/WeaveServer.git"


def get_rpc_base_queue(app_url, name):
    return "/plugins/{}/rpcs/{}".format(app_url, name)


def get_rpc_request_queue(base_queue):
    return base_queue.rstrip('/') + "/request"


def get_rpc_response_queue(base_queue):
    return base_queue.rstrip('/') + "/response"


def create_rpc_queues(base_queue, owner_app, request_schema, response_schema,
                      registry, app_url, allowed_requestor_urls):
        request_queue = get_rpc_request_queue(base_queue)
        response_queue = get_rpc_response_queue(base_queue)

        # Request Queue: allowed_requestor_urls can enqueue but only the app can
        # dequeue.
        request_authorizers = {
            "push": WhitelistAuthorizer(allowed_requestor_urls)
                       if allowed_requestor_urls else AllowAllAuthorizer(),
            "pop": WhitelistAuthorizer([app_url])
        }

        # Response Queue: This is a sessionized queue, so anyone can dequeue,
        # but only the app can enqueue.
        response_authorizers = {
            "push": WhitelistAuthorizer(app_url),
            "pop": AllowAllAuthorizer(),
        }

        # World enqueues into the request queue:
        registry.create_queue(request_queue, owner_app, request_schema, {},
                              'fifo', authorizers=request_authorizers)
        registry.create_queue(response_queue, owner_app, response_schema, {},
                              'sessionized', authorizers=response_authorizers)
        return dict(request_queue=request_queue, response_queue=response_queue)


class RPCInfo(object):
    def __init__(self, app_url, name, desc, apis, base_queue, req_schema,
                 res_schema):
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

    def __init__(self, name, desc, apis, service, channel_registry, owner_app):
        super(RootRPCServer, self).__init__(name, desc, apis, service)
        self.owner_app = owner_app
        self.channel_registry = channel_registry

    def register_rpc(self):
        return create_rpc_queues(SYSTEM_REGISTRY_BASE_QUEUE, self.owner_app,
                                 {}, {}, self.channel_registry,
                                 MESSAGING_SERVER_URL, [])

    def get_appmgr_client(self):
        class DummyClient(object):
            def start(self): pass
            def stop(self): pass

        return DummyClient()

# This class should be thread-safe since RootRPCServer has a single worker to
# process all requests.
class MessagingRPCHub(object):
    APIS_SCHEMA = {"type": "object"}

    def __init__(self, service, channel_registry, app_registry,
                 synonym_registry):
        owner_app = app_registry.get_app_by_url(MESSAGING_SERVER_URL)
        self.rpc = RootRPCServer("app_manager", "Application Manager", [
            ServerAPI("register_rpc", "Register new RPC", [
                ArgParameter("name", "Name of the RPC", str),
                ArgParameter("description", "Description of RPC", str),
                ArgParameter("apis", "Maps of all APIs", self.APIS_SCHEMA),
                ArgParameter("allowed_requestors",
                             "List of app_urls that can call this RPC. Empty " +
                             "list to allow everyone.",
                             {"type": "array", "items": {"type": "string"}})
            ], self.register_rpc),
            ServerAPI("update_rpc", "Update RPC with latest schema.", [
                ArgParameter("name", "Name of the RPC", str),
                ArgParameter("apis", "Maps of all APIs", self.APIS_SCHEMA),
            ], self.update_rpc),
            ServerAPI("unregister_rpc", "Unregister an RPC", [
                ArgParameter("name", "Name of the RPC", str),
            ], self.unregister_rpc),
            ServerAPI("register_plugin", "Register Plugin", [
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
            ServerAPI("register_synonym", "Register a synonym for a channel.", [
                ArgParameter("synonym", "Name of requested synonym", str),
                ArgParameter("target", "Name of channel to map to", str),
            ], self.register_synonym),
        ], service, channel_registry, owner_app)
        self.channel_registry = channel_registry
        self.app_registry = app_registry
        self.synonym_registry = synonym_registry
        self.rpc_registry = {}

    def start(self):
        # TODO: Fix request and response schema everywhere.
        rpc_info = RPCInfo(MESSAGING_SERVER_URL, self.rpc.name,
                           self.rpc.description,
                           {x: y.info for x, y in self.rpc.apis.items()},
                           SYSTEM_REGISTRY_BASE_QUEUE, {}, {})
        self.rpc_registry[(MESSAGING_SERVER_URL, self.rpc.name)] = rpc_info
        self.rpc.start()

    def stop(self):
        self.rpc.stop()

    def register_rpc(self, name, description, apis, allowed_requestors):
        caller_app = get_rpc_caller()
        app_url = caller_app["app_url"]
        base_queue = get_rpc_base_queue(app_url, name)
        request_schema = self.get_request_schema_from_apis(apis)
        response_schema = {}
        owner_app = self.app_registry.get_app_by_url(app_url)

        if (app_url, name) in self.rpc_registry:
            raise ObjectAlreadyExists(name)

        res = create_rpc_queues(base_queue, owner_app, request_schema,
                                response_schema, self.channel_registry, app_url,
                                allowed_requestors)

        rpc_info = RPCInfo(app_url, name, description, apis, base_queue,
                           request_schema, response_schema)

        # Thread safe because MAX_RPC_WORKERS == 1.
        self.rpc_registry[(app_url, name)] = rpc_info
        logger.info("Registered RPC: %s(%s)", name, app_url)
        return res

    def update_rpc(self, name, apis):
        caller_app = get_rpc_caller()
        app_url = caller_app["app_url"]
        rpc_info = self.find_rpc(app_url, name)
        request_queue = get_rpc_request_queue(rpc_info.base_queue)
        response_queue = get_rpc_response_queue(rpc_info.base_queue)
        request_schema = self.get_request_schema_from_apis(apis)
        response_schema = {}
        self.channel_registry.update_channel_schema(request_queue,
                                                    request_schema, {})
        self.channel_registry.update_channel_schema(response_queue,
                                                    response_schema, {})
        return True

    def unregister_rpc(self, name):
        caller_app = get_rpc_caller()
        app_url = caller_app["app_url"]
        base_queue = get_rpc_base_queue(app_url, name)
        self.channel_registry.remove_channel(get_rpc_request_queue(base_queue))
        self.channel_registry.remove_channel(get_rpc_response_queue(base_queue))
        return True

    def register_plugin(self, name, url):
        caller_app = get_rpc_caller()
        if caller_app["app_type"] != "system":
            raise AuthenticationFailed("Only system apps can register plugins.")

        return self.app_registry.register_plugin(name, url)

    def unregister_plugin(self, token):
        caller_app = get_rpc_caller()

        if caller_app.get("app_type") != "system":
            raise AuthenticationFailed("Only system apps can stop plugins.")

        self.app_registry.unregister_plugin(token)
        return True

    def rpc_info(self, url, rpc_name):
        rpc_info = self.find_rpc(url, rpc_name)
        return rpc_info.to_json()

    def register_synonym(self, synonym, target):
        caller_app = get_rpc_caller()
        channel = self.channel_registry.get_channel(target)

        if caller_app["app_url"] != channel.channel_info.owner_app.url:
            raise Unauthorized("Only creator can perform this operation.")

        return self.synonym_registry.register(synonym, target)

    def find_rpc(self, url, name):
        try:
            return self.rpc_registry[(url, name)]
        except KeyError:
            raise ObjectNotFound("RPC not found: " + rpc_name)

    def get_request_schema_from_apis(self, apis):
        return {
            "type": "object",
            "properties": {
                "invocation": {
                    "anyOf": [ServerAPI.from_info(x).schema
                              for x in apis.values()]
                }
            }
        }
