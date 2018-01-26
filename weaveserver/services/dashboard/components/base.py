import logging
from threading import RLock

from flask import request
from flask_socketio import Namespace


logger = logging.getLogger(__name__)


def configure_flask_logging(app):
    for handler in logging.getLogger().handlers:
        app.logger.addHandler(handler)

    logging.getLogger('socketio').setLevel(logging.ERROR)
    logging.getLogger('engineio').setLevel(logging.ERROR)
    logging.getLogger('werkzeug').setLevel(logging.ERROR)


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
        logger.info("WebSocket client connected: %s", request.sid)

    def on_disconnect(self):
        with self.clients_lock:
            self.clients.discard(request.sid)
        logger.info("WebSocket client disconnected: %s", request.sid)

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
