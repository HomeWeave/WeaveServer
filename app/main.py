"""
The main module for HomePiServer. Initializes SocketIO, ServiceManager, NavigationChannel,
View Manager.
"""


import signal
from threading import Thread

import eventlet
from flask import Flask
from flask_socketio import SocketIO

from .controllers import CONTROLLERS
from .core.logger import configure_logging
from .core.websocket_manager import WebSocketManager
from .core.servicemanager import ServiceManager
from .services import SERVICES

eventlet.monkey_patch()

class HomePiServer(object):
    """
    Encapsulates the entire server.
    """
    def __init__(self, config):
        params = {
            "template_folder": "../templates",
            "static_folder": "../static"
        }
        self.flask_app = Flask(__name__, **params)
        self.flask_app.config.from_object(config)
        self.register_blueprints(self.flask_app, CONTROLLERS)

        self.app = SocketIO(self.flask_app)

        self.socket_manager = WebSocketManager(self.app)
        self.service_manager = ServiceManager(SERVICES, self.socket_manager)

        configure_logging(self.flask_app)

        self.start_services()

    def start_services(self):
        """Starts self.service_manager.start() on a new thread."""
        self.service_thread = Thread(target=self.service_manager.start).start()

    @staticmethod
    def register_blueprints(app, params):
        """
        Registers all the blueprints in controllers list.
        Args:
            app: Flask app to register the blueprint with.
            controllers: List like: [(prefix, blueprint), ...]
        """
        for prefix, controller in params:
            app.register_blueprint(controller, url_prefix=prefix)

    def shutdown(self):
        pass

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

def create_app(config=None):
    """ Returns a new instance of HomePiServer."""
    if config is None:
        import app.config
        config = app.config
    app = HomePiServer(config)
    setup_signals(app)
    return app.flask_app, app.app

