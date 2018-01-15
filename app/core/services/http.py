import logging
import os
import socket
import sys
import time
from random import randrange
from threading import Thread
from uuid import uuid4

from flask import Flask, redirect


logger = logging.getLogger(__name__)


def configure_flask_logging(app):
    for handler in logging.getLogger().handlers:
        app.logger.addHandler(handler)

    logging.getLogger('socketio').setLevel(logging.ERROR)
    logging.getLogger('engineio').setLevel(logging.ERROR)
    logging.getLogger('werkzeug').setLevel(logging.ERROR)


class AppHTTPServer(object):
    def __init__(self, service):
        self.unique_id = "http-" + str(uuid4())
        module = sys.modules[service.__module__]
        self.core_dir = os.path.dirname(__file__)
        self.module_dir = os.path.dirname(module.__file__)
        self.flask = Flask(service.__module__, static_url_path='/static')
        self.flask.add_url_rule("/app.js", "sdk-js", self.sdkjs_handler)
        self.flask.add_url_rule("/", "root", self.root_handler)
        self.service = service
        configure_flask_logging(self.flask)

    def sdkjs_handler(self):
        with open(os.path.join(self.core_dir, "sdk.js")) as js_file:
            return js_file.read()

    def root_handler(self):
        return redirect("/static/index.html", code=302)

    def add_rule(self, path, handler):
        self.flask.add_url_rule(path, "custom-" + str(uuid4()), handler)

    def start(self):
        Thread(target=self.launch_server, daemon=True).start()
        Thread(target=self.register_server).start()

    def launch_server(self):
        while True:
            self.port = randrange(40000, 50000)
            try:
                self.flask.run(port=self.port)
            except Exception:
                pass

    def register_server(self):
        while True:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                sock.connect(("localhost", self.port))
                break
            except IOError:
                time.sleep(1)
            finally:
                sock.close()
        logger.info("App Server registered: %s", self.unique_id)
        self.service.app.register_application_server(self)
        logger.info("app info: %s", str(self.service.app.info_message))

    @property
    def info_message(self):
        return {
            "id": self.unique_id,
            "url": "http://{}:{}".format("localhost", self.port)
        }
