"""
The main module for HomePiServer. Initializes SocketIO, ServiceManager,
NavigationChannel, View Manager.
"""

import signal

from .core.registry import Registry
from .core.servicemanager import ServiceManager


class Hulk(object):
    """
    Encapsulates the entire server.
    """
    def __init__(self):
        self.registry = Registry()
        self.service_manager = ServiceManager(self.registry)

    def start(self):
        """Starts self.service_manager.start() on a new thread."""
        self.service_manager.run()

    def shutdown(self):
        self.service_manager.stop()


def setup_signals(app):
    """ Listen for SIGTERM and SIGINIT and calls app.shutdown()"""
    def make_new_handler(prev_handler_func):
        def new_handler(var1, var2):
            app.shutdown()
            if prev_handler_func:
                prev_handler_func(var1, var2)
        return new_handler

    for sig in (signal.SIGTERM, signal.SIGINT):
        prev_handler = signal.getsignal(sig)
        signal.signal(sig, make_new_handler(prev_handler))


def create_app():
    """ Returns a new instance of HomePiServer."""
    app = Hulk()
    setup_signals(app)
    return app
