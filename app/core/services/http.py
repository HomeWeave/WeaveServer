import logging
import os
import socket
import sys
import time
from ipaddress import IPv4Network
from random import randrange
from threading import Thread
from uuid import uuid4

from flask import Flask, redirect

import app.core.netutils as netutils

logger = logging.getLogger(__name__)


def configure_flask_logging(app):
    for handler in logging.getLogger().handlers:
        app.logger.addHandler(handler)

    logging.getLogger('socketio').setLevel(logging.ERROR)
    logging.getLogger('engineio').setLevel(logging.ERROR)
    logging.getLogger('werkzeug').setLevel(logging.ERROR)


def get_server_address(port):
    for ip_obj in netutils.iter_ipv4_addresses():
        net = IPv4Network(ip_obj["addr"] + "/" + ip_obj["netmask"],
                          strict=False)
        if not net.is_loopback and check_ip(ip_obj["addr"], port):
            return ip_obj["addr"]
    return "localhost"


def check_ip(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect(("localhost", port))
        return True
    except IOError:
        return False
    finally:
        sock.close()


class AppHTTPServer(object):
    def __init__(self, service, fa_favicon="cog"):
        self.unique_id = "http-" + service.get_component_name() + str(uuid4())
        module = sys.modules[service.__module__]
        self.core_dir = os.path.dirname(__file__)
        self.module_dir = os.path.dirname(module.__file__)
        self.flask = Flask(service.__module__, static_url_path='/static')
        self.flask.add_url_rule("/app.js", "sdk-js", self.sdkjs_handler)
        self.flask.add_url_rule("/", "root", self.root_handler)
        self.service = service
        self.fa_favicon = fa_favicon
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
                self.flask.run(host="0.0.0.0", port=self.port, debug=False,
                               use_reloader=False)
            except Exception:
                pass

    def register_server(self):
        while True:
            if not check_ip("localhost", self.port):
                time.sleep(1)
            else:
                break
        self.service.app.register_application_server(self)
        logger.info("App Server registered: %s", self.unique_id)

    @property
    def info_message(self):
        url = "http://{}:{}".format(get_server_address(self.port), self.port)
        return {
            "id": self.unique_id,
            "url": url,
            "icon": self.fa_favicon
        }
