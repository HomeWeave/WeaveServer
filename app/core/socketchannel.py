from flask import request
from flask_socketio import Namespace, emit


class ClientSocket(object):
    def __init__(self):
        pass

    #def send_message(

class NavigationChannel(Namespace):
    def __init__(self, namespace, socketio):
        self.socketio = socketio
        self.ns = namespace
        self.display = None #Hack: Will be set from app/main.py.

        self.clients = set()

        super(Namespace, self).__init__(namespace)

    def on_connect(self):
        self.clients.add(request.sid)

    def on_disconnect(self):
        self.clients.remove(request.sid)

    def on_request_view(self, *args):
        self.send_view(self.display.view.html(), room=request.sid)

    def send_view(self, html, room=None):
        self.socketio.emit('view', {"html": html}, room=room, namespace=self.ns)

