import signal
from threading import Thread

from flask import Flask

from .controllers import controllers
from .core import server_timer
from .services import ServiceManager, SERVICES
from .views import view_manager


class HomePiServer(Flask):
    def __init__(self, config):
        params = {
            "template_folder": "../templates"
        }
        super(HomePiServer, self).__init__(__name__, **params)
        self.config.from_object(config)
        self.register_blueprints(controllers)

        server_timer.start()

        self.start_services()

    def start_services(self):
        self.service_manager = ServiceManager(SERVICES, view_manager)
        self.service_thread = Thread(target=self.service_manager.start).start()

    def register_blueprints(self, controllers):
        for prefix, controller in controllers:
            self.register_blueprint(controller, url_prefix=prefix)

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

    return app


