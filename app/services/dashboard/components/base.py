from threading import RLock

from flask import request
from flask_socketio import Namespace


class BaseComponent(Namespace):
    def __init__(self, namespace_url):
        super(BaseComponent, self).__init__(namespace_url)
        self.clients = set()
        self.clients_lock = RLock()

    def activate(self):
        pass

    def deactivate(self):
        pass

    def on_connect(self):
        with self.clients_lock:
            self.clients.add(request.sid)

    def on_disconnect(self):
        with self.clients_lock:
            self.clients.discard(request.sid)

    def notify_all(self, key, obj):
        with self.clients_lock:
            for sid in self.clients:
                self.socketio.emit(key, obj, room=sid, namespace=self.namespace)

    def notify(self, sid, key, obj):
        self.socketio.emit(key, obj, room=sid, namespace=self.namespace)

    def reply(self, key, obj):
        self.socketio.emit(key, obj, room=self.client_id,
                           namespace=self.namespace)

    @property
    def client_id(self):
        return request.sid

    @property
    def connected_clients(self):
        with self.clients_lock:
            return set(self.clients)
