"""
Containamespace classes that handle communication over websocket.
"""
from threading import RLock

from flask import request
from flask_socketio import Namespace


class ClientSocket(object): #pylint: disable=R0903
    """Represents one websocket client"""
    def __init__(self, channel, sid, namespace):
        """
        Args:
            channel: socketio inamespacetance that encaspsulates flask app.
            sid: Session id present in request.sid
            namespace: namespace
        """
        self.sid = sid
        self.namespace = namespace
        self.channel = channel

    def send_message(self, key, data):
        self.channel.emit(key, data, namespace=self.namespace, room=self.sid)

class NavigationChannel(Namespace):
    """Manages all the clients and responds with latest view in self.display"""
    def __init__(self, namespace, socketio):
        """
        Args:
            namespace: Namespace of communication
            socketio: socketio inamespacetance that encaspsulates flask app
        """
        self.client_dict_lock = RLock()
        self.socketio = socketio
        self.namespace = namespace
        self.display = None #Hack: Will be set from app/main.py.

        self.clients = {}

        super(NavigationChannel, self).__init__(namespace)

    def on_connect(self):
        with self.client_dict_lock:
            self.clients[request.sid] = ClientSocket(self.socketio, request.sid, self.namespace)

    def on_disconnect(self):
        with self.client_dict_lock:
            del self.clients[request.sid]

    def on_request_view(self, *_):
        """ Responds to the client with the latest HTML view."""
        data = {"html": self.display.get_view().html()}
        with self.client_dict_lock:
            sock = self.clients[request.sid]

        sock.send_message('view', data)

    def update_view(self, html):
        """ Informs all connected clients about change in the view. """
        with self.client_dict_lock:
            items = list(self.clients.items())
        for _, sock in items:
            data = {"html": html}
            sock.send_message('view', data)

