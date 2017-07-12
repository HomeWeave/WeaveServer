"""
Contains BaseView that acts as a base class for all websocket based views.
"""
import os.path
from threading import RLock
import logging

from flask_socketio import Namespace
from flask import request


logger = logging.getLogger(__name__)


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


class BaseViewWebSocket(Namespace):
    """Manages all the clients and responds with latest view in self.display"""

    def __init__(self, view, namespace, socketio):
        """
        Args:
            namespace: Namespace of communication
            socketio: socketio inamespacetance that encaspsulates flask app
        """
        self.client_dict_lock = RLock()
        self.socketio = socketio
        self.namespace = namespace
        self.view = view
        self.clients = {}

        super(BaseViewWebSocket, self).__init__(namespace)

    def on_connect(self):
        sock = ClientSocket(self.socketio, request.sid, self.namespace)
        with self.client_dict_lock:
            self.clients[request.sid] = sock

    def on_disconnect(self):
        with self.client_dict_lock:
            del self.clients[request.sid]

    def notify_all(self, key, value):
        """ Informs all connected clients about change in the view. """
        with self.client_dict_lock:
            items = list(self.clients.items())
        for _, sock in items:
            sock.send_message(key, value)


class BaseView(object):
    """
    Base class for all the views.
    """
    HTML = "simple.html"
    HTML_BASE_PATH = "templates"

    def __init__(self, main_socket):
        self.main_socket = main_socket
        super().__init__()

    def get_sockets(self):
        """
        Returns a generator of sockets to register/un-register
        when the view is active/inactive
        """
        yield self.main_socket

    def get_namespace(self):
        """
        Returns the namespace of the main_socket.
        """
        return self.main_socket.namespace

