import os
import time

import requests
from weavelib.http.apphttp import AppHTTPServer
from weavelib.messaging import Receiver
from weavelib.rpc import RPCServer, ServerAPI, RPCClient
from weavelib.services import BaseService

from weaveserver.core.services import ServiceManager
from weaveserver.services.appmanager import ApplicationService


class DummyService(BaseService):
    def __init__(self):
        self.rpc_server = RPCServer("name", "desc", [
            ServerAPI("api1", "desc2", [], self.api1),
        ], self)
        self.http = AppHTTPServer(self, None)
        super(DummyService, self).__init__()

    def api1(self):
        return "OK"

    def on_service_start(self):
        self.rpc_server.start()

    def on_service_stop(self):
        self.rpc_server.stop()


class TestApplicationService(object):
    def setup_class(cls):
        os.environ["USE_FAKE_REDIS"] = "TRUE"
        cls.service_manager = ServiceManager()
        cls.service_manager.start_services(["messaging"])
        cls.appmgr = ApplicationService(None)
        cls.appmgr.exited.set()
        cls.appmgr.on_service_start()

        # Wait till it starts.
        receiver = Receiver("/_system/root_rpc/request")
        while True:
            try:
                receiver.start()
            except:
                time.sleep(1)
                pass
            break

    def teardown_class(cls):
        del os.environ["USE_FAKE_REDIS"]
        cls.service_manager.stop()
        cls.appmgr.on_service_stop()

    def setup_method(self):
        self.dummy_service = DummyService()
        self.dummy_service.service_start()

    def teardown_method(self):
        self.dummy_service.service_stop()

    def test_rpc(self):
        rpc = RPCClient(self.dummy_service.rpc_server.info_message)
        rpc.start()
        assert "OK" == rpc["api1"](_block=True)
        rpc.stop()

    def test_http_simple_rule(self):
        main_url = self.dummy_service.http.add_url({"obj": "test"})

        got = requests.get("http://localhost:5000" + main_url).json()
        assert got == {"obj": "test"}

    def test_bad_view(self):
        assert requests.get("http://localhost:5000/view/blh").status_code == 404
