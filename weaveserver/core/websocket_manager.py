"""
There needs to be a way to determine the set of active components that can
talk to JS web socket clients. Since flask-socketio does not provide a way to
cleanly un-register namespace instances, we have to roll out a new "manager".
This module contains `WebSocketManager` that registers and un-registers
namespace instances.
"""

import logging


logger = logging.getLogger(__name__)


class WebSocketManager(object):
    """ Maintains a set of active WS channels. """
    def __init__(self, socketio):
        self.socketio = socketio

    def register(self, namespace):
        try:
            self.socketio.on_namespace(namespace)
        except ValueError:
            raise
        logger.info("Register namespace: %s", namespace.namespace)

    def unregister(self, namespace):
        # Opposite of what happens in self.socketio.on_namespace

        if self.socketio.server:
            del self.socketio.server.namespace_handlers[namespace.namespace]
        else:
            self.socketio.namespace_handlers.remove(namespace)
        logger.info("Removed namespace: %s", namespace.namespace)

    def emit(self, *args, **kwargs):
        self.socketio.emit(*args, **kwargs)

