import hashlib
import os

import requests
from weavelib.http import AppHTTPServer
from weavelib.messaging import WeaveConnection
from weavelib.rpc import RPCServer, ServerAPI, RPCClient
from weavelib.services import BaseService, BackgroundThreadServiceStart

from weaveserver.services.core import CoreService
from weaveserver.services.http import HTTPService

from weaveserver.core.logger import configure_logging


configure_logging()


AUTH = {
    "auth1": {
        "type": "SYSTEM",
        "package": "core",
        "appid": "auth1"
    },
    "auth2": {
        "appid": "auth2",
        "type": "SYSTEM",
        "package": "http"
    },
    "auth3": {
        "appid": "auth3",
        "package": "dummy"
    }
}


class ThreadedHTTPService(BackgroundThreadServiceStart, HTTPService):
    pass


class DummyService(BaseService):
    def __init__(self, token):
        super(DummyService, self).__init__(token)
        self.rpc_server = RPCServer("name", "desc", [
            ServerAPI("api1", "desc2", [], self.api1),
        ], self, self.conn)
        self.http = AppHTTPServer(self.conn, self)

    def api1(self):
        return [200, "OK"]

    def on_service_start(self):
        self.rpc_server.start()
        self.http.start()
        self.relative_url = self.http.register_folder("test_dir")

    def on_service_stop(self):
        self.http.stop()
        self.rpc_server.stop()


class TestHTTPService(object):
    def setup_class(cls):
        cls.core_service = CoreService("auth1",
                                       {"core_config": {}, "apps": AUTH})
        cls.core_service.service_start()
        cls.core_service.wait_for_start(30)

        cls.core_service.message_server.register_application(AUTH["auth2"])
        cls.core_service.message_server.register_application(AUTH["auth3"])

        cls.conn = WeaveConnection.local()
        cls.conn.connect()

        cls.service = ThreadedHTTPService("auth2", None)
        cls.service.service_start()
        cls.service.wait_for_start(30)

    def teardown_class(cls):
        cls.service.service_stop()
        cls.core_service.service_stop()

    def setup_method(self):
        self.dummy_service = DummyService("auth3")
        self.dummy_service.service_start()

    def teardown_method(self):
        self.dummy_service.service_stop()

    def test_simple_rpc(self):
        rpc = RPCClient(self.conn, self.dummy_service.rpc_server.info_message)
        rpc.start()
        assert [200, "OK"] == rpc["api1"](_block=True)
        rpc.stop()

    def test_multiple_rpcs(self):
        obj = {
            "package_name": "dummy",
            "rpc_name": "name",
            "api_name": "api1",
            "args": [],
            "kwargs": {}
        }
        url = "http://localhost:5000/api/rpc"
        for _ in range(10):
            res = requests.post(url, json=obj).json()
            assert res == [200, "OK"]

    def test_rpc_with_unknown_package(self):
        obj = {
            "package_name": "unknown",
            "rpc_name": "name",
            "api_name": "api1",
            "args": [],
            "kwargs": {}
        }
        url = "http://localhost:5000/api/rpc"
        res = requests.post(url, json=obj).json()
        assert res == {"error": "RPC not found."}

    def test_http_simple_request(self):
        base_url = "http://localhost:5000" + self.dummy_service.relative_url

        url = base_url + "/index.json"
        resp = requests.get(url, headers={"host": "http://localhost:1234/"})
        assert resp.json()["hello"] == "world"

        url = base_url + "/test.csv"
        resp = requests.get(url)
        assert resp.text == "a,b,c\n"
        assert resp.headers["Content-Type"] == "text/csv; charset=UTF-8"

    def test_resource_creation(self):
        src = os.path.join(os.path.dirname(__file__), "test_dir")
        dest = os.path.join(self.service.plugin_dir.name, "dummy")
        src_files = sorted(y for x in os.walk(src) for y in x[2])
        dest_files = sorted(y for x in os.walk(dest) for y in x[2])

        assert src_files == dest_files

        for rel_path in src_files:
            with open(os.path.join(src, rel_path), "rb") as src_inp:
                src_hash = hashlib.md5(src_inp.read()).hexdigest()
            with open(os.path.join(dest, rel_path), "rb") as dest_inp:
                dest_hash = hashlib.md5(dest_inp.read()).hexdigest()

            assert src_hash == dest_hash
