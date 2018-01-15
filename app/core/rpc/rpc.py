import logging
from concurrent.futures import ThreadPoolExecutor
from threading import Thread, RLock, Event
from uuid import uuid4

from app.core.messaging import Sender, Receiver, Creator
from app.core.rpc.api import API, ArgParameter, KeywordParameter


logger = logging.getLogger(__name__)


def api_group_schema(apis):
    return {
        "anyOf": [x.schema for x in apis]
    }


class RemoteAPIError(RuntimeError):
    """Raised to indicate exception thrown by remote API."""


class ClientAPI(API):
    def __init__(self, name, desc, params, handler):
        super(ClientAPI, self).__init__(name, desc, params)
        self.handler = handler

    def __call__(self, *args, _block=False, _callback=None, **kwargs):
        obj = self.validate_call(*args, **kwargs)
        return self.handler(obj, block=_block, callback=_callback)

    @staticmethod
    def from_info(info, handler):
        api = ClientAPI(info["name"], info["description"], [], handler)
        api.args = [ArgParameter.from_info(x) for x in info.get("args", [])]
        api.kwargs = [KeywordParameter.from_info(x) for x in
                      info.get("kwargs", {}).values()]
        return api


class ServerAPI(API):
    def __init__(self, name, desc, params, handler):
        super(ServerAPI, self).__init__(name, desc, params)
        self.handler = handler

    def __call__(self, *args, **kwargs):
        self.validate_call(*args, **kwargs)
        return self.handler(*args, **kwargs)


class RPC(object):
    def __init__(self, name, description, apis):
        self.name = name
        self.description = description
        self.apis = {x.name: x for x in apis}

    def __getitem__(self, name):
        return self.apis[name]

    @property
    def request_schema(self):
        return api_group_schema(self.apis.values())

    @property
    def response_schema(self):
        return {"type": "object"}


class RPCReceiver(Receiver):
    def __init__(self, component, queue, host="localhost"):
        super(RPCReceiver, self).__init__(queue, host=host)
        self.component = component

    def on_message(self, msg):
        self.component.on_rpc_message(msg)


class RPCServer(RPC):
    MAX_RPC_WORKERS = 5

    def __init__(self, name, description, apis, service):
        super(RPCServer, self).__init__(name, description, apis)
        self.service = service
        self.unique_id = "rpc-" + str(uuid4())
        self.queue = service.get_service_queue_name("apis/" + self.unique_id)
        self.request_queue = self.queue + "/request"
        self.response_queue = self.queue + "/response"

        self.sender = Sender(self.response_queue)
        self.receiver = RPCReceiver(self, self.request_queue)
        self.receiver_thread = Thread(target=self.receiver.run)

        self.executor = ThreadPoolExecutor(self.MAX_RPC_WORKERS)

    def start(self):
        creator = Creator()
        creator.start()
        creator.create({
            "queue_name": self.request_queue,
            "request_schema": self.request_schema
        })

        creator.create({
            "queue_name": self.response_queue,
            "request_schema": self.response_schema
        })

        self.sender.start()
        self.receiver.start()
        self.receiver_thread.start()

        self.service.app.register_rpc_server(self)

    def stop(self):
        # TODO: Delete the queue, too.

        self.receiver.stop()
        self.receiver_thread.join()

        self.executor.shutdown()

    def on_rpc_message(self, obj):
        def make_done_callback(request_id, cmd):
            def callback(future):
                ex = future.exception()
                if ex:
                    logger.warn("Internal API raised Exception.", ex)
                    self.sender.send({
                        "id": request_id,
                        "command": cmd,
                        "error": "Internal API Error."
                    })
                    return

                self.sender.send({
                    "id": request_id,
                    "command": cmd,
                    "result": future.result()
                })
            return callback

        request_id = obj["id"]
        cmd = obj["command"]
        try:
            api = self[cmd]
        except KeyError:
            self.sender.send({
                "id": request_id,
                "result": False,
                "error": "API not found."
            })
            return

        args = obj.get("args", [])
        kwargs = obj.get("kwargs", {})
        future = self.executor.submit(api, *args, **kwargs)
        future.add_done_callback(make_done_callback(request_id, cmd))

    @property
    def info_message(self):
        return {
            "name": self.name,
            "description": self.description,
            "apis": {name: api.info for name, api in self.apis.items()},
            "uri": self.queue
        }


class RPCClient(RPC):
    def __init__(self, rpc_info):
        name = rpc_info["name"]
        description = rpc_info["description"]
        apis = [self.get_api_call(x) for x in rpc_info["apis"].values()]
        super(RPCClient, self).__init__(name, description, apis)

        self.sender = Sender(rpc_info["uri"] + "/request")
        self.receiver = RPCReceiver(self, rpc_info["uri"] + "/response")
        self.receiver_thread = Thread(target=self.receiver.run)

        self.callbacks = {}
        self.callbacks_lock = RLock()

    def start(self):
        self.sender.start()
        self.receiver.start()
        self.receiver_thread.start()

    def stop(self):
        self.sender.close()
        self.receiver.stop()
        self.receiver_thread.join()

    def get_api_call(self, obj):
        def make_blocking_callback(event, response_arr):
            def callback(obj):
                response_arr.append(obj)
                event.set()
            return callback

        def on_invoke(obj, block, callback):
            msg_id = obj["id"]

            if block:
                res_arr = []
                event = Event()
                callback = make_blocking_callback(event, res_arr)

            if callback:
                with self.callbacks_lock:
                    self.callbacks[msg_id] = callback

            self.sender.send(obj)
            if not block:
                return

            event.wait()

            if "result" in res_arr[0]:
                return res_arr[0]["result"]
            else:
                raise RemoteAPIError(res_arr[0].get("error"))

        return ClientAPI.from_info(obj, on_invoke)

    def on_rpc_message(self, msg):
        with self.callbacks_lock:
            callback = self.callbacks.pop(msg["id"])

        if not callback:
            return

        callback(msg)
