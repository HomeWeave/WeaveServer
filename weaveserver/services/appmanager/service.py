import logging
from threading import Event
from uuid import uuid4

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

        creator = Creator()
        creator.start()
        creator.create({
            "queue_name": request_queue,
            "request_schema": Draft4Validator.META_SCHEMA
        })

        creator.create({
            "queue_name": response_queue,
            "queue_type": "sessionized",
            "request_schema": {}
        })

        return dict(request_queue=request_queue, response_queue=response_queue)


class ApplicationRPC(object):
    def __init__(self):
        self.rpc = RootRPCServer("app_manager", "Application Manager", [
            ServerAPI("register_rpc", "Register new RPC", [
                ArgParameter("name", "Name of the RPC", str),
                ArgParameter("description", "Description of RPC", str),
                ArgParameter("request_schema", "JSONSchema of request",
                             Draft4Validator.META_SCHEMA),
                ArgParameter("response_schema", "JSONSchema of response",
                             Draft4Validator.META_SCHEMA),
            ], self.register_rpc)
        ])
        self.queue_creator = Creator()

    def start(self):
        self.rpc.start()
        self.queue_creator.start()

    def stop(self):
        self.rpc.stop()
        self.queue_creator.stop()

    def register_rpc(self, name, description, request_schema, response_schema):
        print("Request to register..")
        base_queue = "/components/{}/rpcs/{}".format(str(uuid4()), name)
        request_queue = base_queue + "/request"
        response_queue = base_queue + "/response"

        self.queue_creator.create({
            "queue_name": request_queue,
            "request_schema": request_schema,
        })

        self.queue_creator.create({
            "queue_name": response_queue,
            "request_schema": response_schema
        })

        return dict(request_queue=request_queue, response_queue=response_queue)


class ApplicationService(BackgroundProcessServiceStart, BaseService):
    def __init__(self, config):
        self.app = ApplicationRPC()
        self.exited = Event()
        super().__init__()

    def get_component_name(self):
        return "weaveserver.services.appmanager"

    def on_service_start(self, *args, **kwargs):
        self.app.start()
        self.notify_start()
        self.exited.wait()

    def on_service_stop(self):
        self.exited.set()
        self.app.stop()
