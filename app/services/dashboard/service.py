import logging

from flask import Flask
from flask_socketio import SocketIO

from app.core.services import BaseService, BackgroundProcessServiceStart

from .controllers import CONTROLLERS

def configure_flask_logging(app):
    for handler in logging.getLogger().handlers:
        app.logger.addHandler(handler)


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

        self.app.run(self.flask_app, host="0.0.0.0", debug=True,
                     use_reloader=False)

    def get_component_name(self):
        return "dashboard"

    def on_service_stop(self):
        self.flask_app.shutdown()
