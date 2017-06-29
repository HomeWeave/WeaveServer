from gevent import monkey
import signal
from threading import Thread
import json

monkey.patch_all()


from flask import Flask
from flask_socketio import SocketIO

from .controllers import controllers
from .core import server_timer
from .core.socketchannel import NavigationChannel
from .core.logger import configure_logging
from .services import ServiceManager, SERVICES
from .views import ViewManager


class HomePiServer(object):
    def __init__(self, config):
        params = {
            "template_folder": "../templates",
            "static_folder": "../static"
        }
        self.flask_app = Flask(__name__, **params)
        self.flask_app.config.from_object(config)
        self.register_blueprints(self.flask_app, controllers)

        self.app = SocketIO(self.flask_app)

        self.nav_channel = NavigationChannel("/navigation", self.app)
        self.app.on_namespace(self.nav_channel)

        self.view_manager = ViewManager(self.nav_channel)
        self.nav_channel.display = self.view_manager

        self.service_manager = ServiceManager(SERVICES, self.view_manager)

        configure_logging(self.flask_app)

        server_timer.start()

        self.start_services()

    def start_services(self):
        self.service_thread = Thread(target=self.service_manager.start).start()

    def register_blueprints(self, app, controllers):
        for prefix, controller in controllers:
            app.register_blueprint(controller, url_prefix=prefix)

    def shutdown(self):
        print("Shutting down..")
        server_timer.stop()

def create_app(config=None):
    if config is None:
        import app.config
        config = app.config
    app = HomePiServer(config)


    for sig in (signal.SIGTERM, signal.SIGINT):
        prev_handler = signal.getsignal(sig)

    def sig_handler(x, y, prevFn):
        app.shutdown()
        if prevFn:
            prevFn(x, y)

    signal.signal(sig, lambda x, y: sig_handler(x, y, prev_handler))

    return app.flask_app, app.app

