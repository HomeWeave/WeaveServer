import time

import requests
from weavelib.messaging import Receiver
from weavelib.rpc import RPCServer, ServerAPI
from weavelib.services import BaseService

from weaveserver.core.services import ServiceManager
from weaveserver.services.appmanager import ApplicationService


AUTH = {
    "auth1": {
        "type": "SYSTEM",
        "appid": "appmgr"
    },
    "auth2": {
        "appid": "appid2",
        "package": "p"
    }
}


class DummyService(BaseService):
    def __init__(self, token):
        super(DummyService, self).__init__(token)
        self.rpc_server = RPCServer("name", "desc", [
            ServerAPI("api1", "desc2", [], self.api1),
        ], self)

    def api1(self):
        return "OK"

    def on_service_start(self):
        self.rpc_server.start()

    def on_service_stop(self):
        self.rpc_server.stop()


class TestHTTPService(object):
    def setup_class(cls):
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
        cls.service_manager.stop()
        cls.appmgr.on_service_stop()

    def setup_method(self):
        self.dummy_service = DummyService("auth2")
        self.dummy_service.service_start()

    def teardown_method(self):
        self.dummy_service.service_stop()

    def test_http_rpc(self):
        obj = {
            "package_name": "p",
            "rpc_name": "name",
            "api_name": "api1",
            "args": [],
            "kwargs": {}
        }
        url = "http://localhost:5000/api/rpc"
        for _ in range(1):
            res = requests.post(url, json=obj).json()
            assert res == "OK"

