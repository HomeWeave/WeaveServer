import logging
import time
from threading import Thread, RLock

from app.core.messaging import Receiver, Sender
from app.core.rpc import RPCClient

from .base import BaseComponent

logger = logging.getLogger(__name__)


class AppLister(object):
    def __init__(self, shell_component):
        self.apps = []
        self.shell_component = shell_component
        self.app_list_receiver = Receiver("/_system/applications")

    def start(self):
        self.app_list_receiver.on_message = self.process_app_list_message
        self.app_list_receiver.start()

        self.receiver_thread = Thread(target=self.app_list_receiver.run)
        self.receiver_thread.start()

    def stop(self):
        self.app_list_receiver.stop()
        self.receiver_thread.join()

    def process_app_list_message(self, msg):
        self.apps = msg
        for obj in self.apps.values():
            obj["kind"] = "APP"

        self.shell_component.notify_all('dock_apps', self.apps)


class WebSocketReceiver(Receiver):
    def __init__(self, queue, component):
        self.component = component
        self.clients = set()
        self.clients_lock = RLock()
        self.thread = Thread(target=self.run)
        super(WebSocketReceiver, self).__init__(queue)

    def start(self):
        super(WebSocketReceiver, self).start()
        self.thread.start()
        Thread(target=self.clean_clients, daemon=True).start()

    def stop(self):
        super(WebSocketReceiver, self).stop()
        self.thread.join()

    def register(self, sid):
        with self.clients_lock:
            self.clients.add(sid)

    def unregister(self, sid):
        with self.clients_lock:
            self.clients.discard(sid)

    def on_message(self, obj):
        with self.clients_lock:
            clients = set(self.clients)

        msg = {
            "queue": self.queue,
            "data": obj
        }
        for sid in clients:
            self.component.notify(sid, "messaging", msg)

    def clean_clients(self):
        while True:
            time.sleep(30)
            with self.clients_lock:
                self.clients.difference_update(self.component.connected_clients)


class ShellComponent(BaseComponent):
    def __init__(self, ws_manager):
        super(ShellComponent, self).__init__("/shell")
        self.ws_manager = ws_manager
        self.app_lister = AppLister(self)

        self.rpcs = {}
        self.rpcs_lock = RLock()

        self.receivers = {}
        self.receivers_lock = RLock()

    def activate(self):
        self.app_lister.start()

    def deactivate(self):
        self.app_lister.stop()
        with self.receivers_lock:
            for _, receiver in self.receivers:
                receiver.stop()

        with self.rpcs_lock:
            for _, rpc in self.rpcs:
                rpc.stop()

    def on_list_apps(self, msg):
        self.reply('dock_apps', self.app_lister.apps)

    def on_messaging(self, obj):
        queue = obj["queue"]
        data = obj["data"]
        sender = Sender(queue)
        sender.start()
        logger.info("Sent Message to %s: %s", queue, str(data))
        sender.send(data)
        sender.close()

    def on_queue_receive(self, obj):
        receiver = self.get_receiver(obj["queue"])
        receiver.register(self.client_id)
        logger.info("Listening on queue: %s", obj["queue"])

    def on_rpc(self, obj):
        client_id = self.client_id
        request_id = obj["id"]
        payload = obj["rpc"]

        def callback(res):
            self.notify(client_id, 'rpc', {
                "id": request_id,
                "result": res
            })

        uri = payload.get("uri")
        args = payload.get("args", [])
        kwargs = payload.get("kwargs", {})
        func = payload.get("func")

        rpc = self.get_rpc(uri)
        rpc[func](*args, _callback=callback, **kwargs)

    def on_disconnect(self):
        super(ShellComponent, self).on_disconnect()
        with self.receivers_lock:
            items = self.receivers.items
            temp = {x: y for x, y in items() if x[0] != self.client_id}
            self.receivers = temp

    def get_receiver(self, queue):
        with self.receivers_lock:
            key = (self.client_id, queue)
            if key in self.receivers:
                return self.receivers[key]
            self.receivers[key] = WebSocketReceiver(queue, self)
            self.receivers[key].start()
            return self.receivers[key]

    def get_rpc(self, uri):
        with self.rpcs_lock:
            if uri in self.rpcs:
                return self.rpcs[uri]

            cur_rpc = None
            for app_info in self.app_lister.apps.values():
                for rpc in app_info["rpcs"].values():
                    if rpc["uri"] == uri:
                        cur_rpc = rpc
                        break

            rpc = RPCClient(cur_rpc)
            self.rpcs[uri] = rpc
            rpc.start()
            logger.info("Started RPC to: %s", uri)
        return rpc
