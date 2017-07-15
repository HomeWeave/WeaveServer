"""
Has classes to extend applications from.
"""

from threading import RLock
import logging
import sys
import os.path

from flask_socketio import Namespace, emit
from flask import request


logger = logging.getLogger(__name__)


class BaseCommandsListener(object):
    """
    Base class for all commands listener.
    """

    def on_command(self, command):
        """
        Invoked by the ShellService upon an input.
        """
        pass

    def list_commands(self):
        yield from ()


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


class BaseWebSocket(Namespace):
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
        self.clients = {}

        super().__init__(namespace)

    def on_connect(self):
        sock = ClientSocket(self.socketio, request.sid, self.namespace)
        with self.client_dict_lock:
            self.clients[request.sid] = sock

    def on_disconnect(self):
        with self.client_dict_lock:
            del self.clients[request.sid]

    def reply_all(self, key, value):
        """ Informs all connected clients about change in the view. """
        with self.client_dict_lock:
            items = list(self.clients.items())
        for _, sock in items:
            sock.send_message(key, value)

    def reply(self, key, value):
        emit(key, value)


class BaseApp(object):
    """
    Base class for all applications
    """

    ICON = "fa-pencil-square-o"
    NAME = ""
    DESCRIPTION = ""

    def __init__(self, main_socket, command_listener):
        self.main_socket = main_socket
        self.command_listener = command_listener

    def name(self):
        return self.NAME or self.id()

    def id(self):
        return self.__class__.__module__ + "." + self.__class__.__name__

    def icon(self):
        return self.ICON

    def description(self):
        return self.DESCRIPTION or ""

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

    def get_command_listener(self):
        return self.command_listener

    def html(self):
        """
        Applications must override this function such that it returns the HTML string
        of the app.
        """
        return ""

    def start(self):
        pass

    def get_file(self, path):
        app_file = sys.modules[self.__class__.__module__].__file__
        return os.path.join(os.path.dirname(app_file), path)

