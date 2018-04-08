import json
import os
import re
import time

import requests
from weavelib.http import AppHTTPServer
from weavelib.messaging import Receiver
from weavelib.rpc import RPCServer, ServerAPI, RPCClient
from weavelib.services import BaseService

from weaveserver.core.services import ServiceManager
from weaveserver.services.appmanager import ApplicationService


AUTH = {
    "auth1": {
        "type": "SYSTEM",
        "appid": "appmgr"
    },
    "auth2": {
        "appid": "appid2"
    }
}


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
        self.relative_url = self.http.register_folder("test_dir")

    def on_service_stop(self):
        self.rpc_server.stop()


class TestApplicationService(object):
    def setup_class(cls):
        os.environ["USE_FAKE_REDIS"] = "TRUE"
        cls.service_manager = ServiceManager()
        cls.service_manager.apps = AUTH
        cls.service_manager.start_services(["messaging"])
        cls.appmgr = ApplicationService("auth1", {"apps": AUTH})
        cls.appmgr.exited.set()
        cls.appmgr.on_service_start()

        # Wait till it starts.
        receiver = Receiver("/_system/root_rpc/request")
        while True:
            try:
                receiver.start()
                break
            except:
                time.sleep(1)

    def teardown_class(cls):
        del os.environ["USE_FAKE_REDIS"]
        cls.service_manager.stop()
        cls.appmgr.on_service_stop()

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

    def test_http_simple_request(self):
        base_url = "http://localhost:5000" + self.dummy_service.relative_url

        url = base_url + "/index.json"
        resp = requests.get(url, headers={"host": "http://localhost:1234/"})
        assert resp.headers["Content-Type"] == "application/vnd.weaveview+json"
        assert resp.json() == {
            "hello": "world",
            "url": "http://localhost:1234/views/appid2/x"
        }

        url = base_url + "/test.csv"
        resp = requests.get(url)
        assert resp.text == "a,b,c\n"
        assert resp.headers["Content-Type"] == "text/csv"

    def test_http_root(self):
        resp = requests.get("http://localhost:5000/root.json",
                            headers={"host": "http://localhost:1234/"})

        assert resp.headers["Content-Type"] == "application/vnd.weaveview+json"
        got = resp.text

        base_url = "http://localhost:5000" + self.dummy_service.relative_url
        url = base_url + "/expected.json"
        resp = requests.get(url, headers={"host": "http://localhost:1234/"})
        expected = resp.text

        remove_uuid = re.compile('[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-' +
                                 '[a-f0-9]{4}-[a-f0-9]{12}')
        got = json.loads(remove_uuid.sub('', got))
        expected = json.loads(remove_uuid.sub('', expected))

        assert got == expected
