from threading import RLock

from flask import request
from flask_socketio import Namespace, emit


class ClientSocket(object):
    def __init__(self, channel, sid, ns):
        self.sid = sid
        self.ns = ns
        self.channel = channel

    def send_message(self, key, data):
        self.channel.emit(key, data, namespace=self.ns, room=self.sid)

class NavigationChannel(Namespace):
    def __init__(self, namespace, socketio):
        self.client_dict_lock = RLock()
        self.socketio = socketio
        self.ns = namespace
        self.display = None #Hack: Will be set from app/main.py.

        self.clients = {}

        super(Namespace, self).__init__(namespace)

    def on_connect(self):
        with self.client_dict_lock:
            self.clients[request.sid] = ClientSocket(self.socketio, request.sid, self.ns)

    def on_disconnect(self):
        with self.client_dict_lock:
            del self.clients[request.sid]

    def on_request_view(self, *args):
        data = {"html": self.display.get_view().html()}
        with self.client_dict_lock:
            sock = self.clients[request.sid]

        sock.send_message('view', data)

    def update_view(self, html):
        with self.client_dict_lock:
            items = list(self.clients.items())
        for sid, sock in items:
            data = {"html": html}
            sock.send_message('view', data)

