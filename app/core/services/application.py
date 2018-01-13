from threading import RLock
from uuid import uuid4

from app.core.messaging import Sender


class Application(object):
    APPLICATION_INFO_QUEUE = "/_system/applications"

    def __init__(self, service):
        self.service = service
        self.unique_id = "app-" + str(uuid4())
        self.rpc_servers = {}
        self.app_servers = {}
        self.info_lock = RLock()

    def register_rpc_server(self, rpc_server):
        with self.info_lock:
            names = {x.name for x in self.rpc_servers.values()}
            if rpc_server.name in names:
                raise ValueError("Name already exists: " + rpc_server.name)
            self.rpc_servers[rpc_server.queue] = rpc_server
            self.push_update()

    def register_application_server(self, server):
        with self.info_lock:
            self.app_servers[server.unique_id] = server
            self.push_update()

    def push_update(self):
        sender = Sender(self.APPLICATION_INFO_QUEUE)
        sender.start()
        sender.send(self.info_message, headers={"KEY": self.unique_id})
        sender.close()

    @property
    def info_message(self):
        with self.info_lock:
            apps = self.app_servers.values()
            rpcs = self.rpc_servers.values()
            return {
                "apps": {x.unique_id: x.info_message for x in apps},
                "rpcs": {x.unique_id: x.info_message for x in rpcs},
                "service_queue_prefix": self.service.get_service_queue_name("")
            }
