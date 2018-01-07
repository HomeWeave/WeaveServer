import logging
import os
import signal

from flask import Flask
from flask_socketio import SocketIO

from app.core.services import BaseService, BackgroundProcessServiceStart

from .controllers import CONTROLLERS
from .websocket_manager import WebSocketManager
from .components.shell_component import ShellComponent


def configure_flask_logging(app):
    for handler in logging.getLogger().handlers:
        app.logger.addHandler(handler)

    logging.getLogger('socketio').setLevel(logging.ERROR)
    logging.getLogger('engineio').setLevel(logging.ERROR)


class DashboardService(BackgroundProcessServiceStart, BaseService):
    def on_service_start(self):
        params = {
            "template_folder": "templates",
            "static_folder": "static"
        }
        self.flask_app = Flask(__name__, **params)

        for prefix, controller in CONTROLLERS:
            self.flask_app.register_blueprint(controller, url_prefix=prefix)

        configure_flask_logging(self.flask_app)

        self.app = SocketIO(self.flask_app)
        self.ws_manager = WebSocketManager(self.app)
        self.shell = ShellComponent(self.ws_manager)
        self.ws_manager.register(self.shell)

        self.shell.activate()

        self.notify_start()

        self.app.run(self.flask_app, host="0.0.0.0", debug=True,
                     use_reloader=False)

    def get_component_name(self):
        return "dashboard"

    def on_service_stop(self):
        os.kill(os.getpid(), signal.SIGKILL)
