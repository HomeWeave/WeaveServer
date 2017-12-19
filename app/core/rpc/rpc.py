from threading import Thread
from uuid import uuid4

from app.core.messaging import Sender, Receiver, Creator
from app.core.rpc.api import API, ArgParameter, KeywordParameter


def api_group_schema(apis):
    return {
        "anyOf": [x.schema for x in apis]
    }


class ClientAPI(API):
    def __init__(self, name, desc, params, handler):
        super(ClientAPI, self).__init__(name, desc, params)
        self.handler = handler

    def __call__(self, *args, **kwargs):
        obj = self.validate_call(*args, **kwargs)
        return self.handler(obj)

    @staticmethod
    def from_info(info, handler):
        api = ClientAPI(info["name"], info["description"], [], handler)
        api.id = info["id"]
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
        self.apis_by_id = {x.id: x for x in apis}

    @property
    def receiving_schema(self):
        return api_group_schema(self.apis.values())


class RPCReceiver(Receiver):
    def __init__(self, server, queue, host="localhost"):
        super(RPCReceiver, self).__init__(queue, host=host)
        self.server = server

    def on_message(self, obj):
        self.server.execute_command(obj)

class RPCServer(RPC):
    def __init__(self, name, description, apis, service):
        super(RPCServer, self).__init__(name, description, apis)
        self.queue_name = service.get_service_queue_name("/apis/" + str(uuid4()))
        self.receiver = RPCReceiver(self, self.queue_name)
        self.receiver_thread = Thread(target=self.receiver.run)

    def start(self):
        creator = Creator()
        creator.start()
        creator.create({
            "queue_name": self.queue_name,
            "request_schema": self.receiving_schema
        })

        self.receiver.start()
        self.receiver_thread.start()

    def stop(self):
        self.receiver.stop()
        self.receiver_thread.join()

    def execute_command(self, obj):
        cmd = obj["command"]
        api = self.apis_by_id[cmd]
        api(*obj.get("args", []), **obj.get("kwargs", {}))

    @property
    def info_message(self):
        return {
            "name": self.name,
            "description": self.description,
            "apis": {uid: api.info for uid, api in self.apis_by_id.items()},
            "uri": self.queue_name
        }


class RPCClient(RPC):
    def __init__(self, rpc_info):
        self.sender = Sender(rpc_info["uri"])
        name = rpc_info["name"]
        description = rpc_info["description"]
        apis = [self.get_api_call(x) for x in rpc_info["apis"].values()]
        super(RPCClient, self).__init__(name, description, apis)

    def start(self):
        self.sender.start()

    def get_api_call(self, obj):
        return ClientAPI.from_info(obj, self.sender.send)
