import time

from weavelib.messaging import Receiver
from weavelib.rpc import RPCServer, ServerAPI, RPCClient
from weavelib.services import BaseService

from weaveserver.services.core import CoreService


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


class TestApplicationService(object):
    def setup_class(cls):
        cls.core_service = CoreService("auth1",
                                       {"core_config": {}, "apps": AUTH})
        cls.core_service.service_start()
        assert cls.core_service.wait_for_start(30)

        # Wait till it starts.
        receiver = Receiver("/_system/root_rpc/request")
        while True:
            try:
                receiver.start()
                break
            except:
                time.sleep(1)

        cls.core_service.message_server.register_application(AUTH["auth2"])
        cls.dummy_service = DummyService("auth2")
        cls.dummy_service.service_start()

    def teardown_class(cls):
        cls.core_service.service_stop()
        cls.dummy_service.service_stop()

    def test_rpc(self):
        rpc = RPCClient(self.dummy_service.rpc_server.info_message)
        rpc.start()
        assert "OK" == rpc["api1"](_block=True)
        rpc.stop()

    def test_rpc_info(self):
        info = self.dummy_service.rpc_client["rpc_info"]("p", "name",
                                                         _block=True)
        actual_info = self.dummy_service.rpc_server.info_message
        assert info["request_queue"] == actual_info["request_queue"]
        assert info["response_queue"] == actual_info["response_queue"]

    def disabled_test_build_info(self):
        build_version = self.dummy_service.rpc_client["build_info"](_block=True)
        assert build_version == "latest"
