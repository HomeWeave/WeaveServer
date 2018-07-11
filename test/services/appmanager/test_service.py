import time

import requests
from weavelib.http import AppHTTPServer
from weavelib.messaging import Receiver
from weavelib.rpc import RPCServer, ServerAPI, RPCClient
from weavelib.services import BaseService, BackgroundThreadServiceStart

from weaveserver.services.core import CoreService
from weaveserver.services.http import HTTPService


AUTH = {
    "auth1": {
        "type": "SYSTEM",
        "appid": "auth1"
    },
    "auth2": {
        "appid": "auth2",
        "package": "p"
    }
}


class ThreadedHTTPService(BackgroundThreadServiceStart, HTTPService):
    pass


class DummyService(BaseService):
    def __init__(self, token):
        super(DummyService, self).__init__(token)
        self.rpc_server = RPCServer("name", "desc", [
            ServerAPI("api1", "desc2", [], self.api1),
        ], self)
        self.http = AppHTTPServer(self)

    def api1(self):
        return "OK"

    def on_service_start(self):
        self.rpc_server.start()
        self.http.start()
        self.relative_url = self.http.register_folder("test_dir")

    def on_service_stop(self):
        self.http.stop()
        self.rpc_server.stop()


class TestHTTPService(object):
    def setup_class(cls):
        cls.core_service = CoreService("auth1", {"core_config": {}})
        cls.core_service.service_start()
        cls.core_service.wait_for_start(30)

        cls.core_service.message_server.register_application(AUTH["auth2"])

        # Wait till it starts.
        receiver = Receiver("/_system/root_rpc/request")
        while True:
            try:
                receiver.start()
                break
            except:
                time.sleep(1)

        cls.service = ThreadedHTTPService("auth2", None)
        cls.service.service_start()
        cls.service.wait_for_start(30)

    def teardown_class(cls):
        cls.service.service_stop()
        cls.core_service.service_stop()

    def setup_method(self):
        self.dummy_service = DummyService("auth2")
        self.dummy_service.service_start()

    def teardown_method(self):
        self.dummy_service.service_stop()

    def test_rpc(self):
        rpc = RPCClient(self.dummy_service.rpc_server.info_message)
        rpc.start()
        assert "OK" == rpc["api1"](_block=True)
        rpc.stop()

    def disabled_test_http_simple_request(self):
        base_url = "http://localhost:5000" + self.dummy_service.relative_url

        url = base_url + "/index.json"
        resp = requests.get(url, headers={"host": "http://localhost:1234/"})
        assert resp.json()["hello"] == "world"

        url = base_url + "/test.csv"
        resp = requests.get(url)
        assert resp.text == "a,b,c\n"
        assert resp.headers["Content-Type"] == "text/csv; charset=UTF-8"

    def test_rpc_info(self):
        info = self.dummy_service.rpc_client["rpc_info"]("p", "name",
                                                         _block=True)
        actual_info = self.dummy_service.rpc_server.info_message
        assert info["request_queue"] == actual_info["request_queue"]
        assert info["response_queue"] == actual_info["response_queue"]
