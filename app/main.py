import signal

from flask import Flask

from .controllers import controllers
from .core import server_timer

class HomePiServer(Flask):
    def __init__(self, config):
        super(HomePiServer, self).__init__(__name__)
        self.config.from_object(config)
        self.register_blueprints(controllers)
        server_timer.start()

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


