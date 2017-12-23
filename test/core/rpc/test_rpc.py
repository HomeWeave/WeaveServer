import os
from threading import Event

from app.core.rpc import RPCServer, RPCClient, ServerAPI
from app.core.rpc import ArgParameter, KeywordParameter
from app.core.services import ServiceManager
from app.core.logger import configure_logging

configure_logging()


CONFIG = {
    "redis_config": {
        "USE_FAKE_REDIS": True
    },
    "queues": {
        "custom_queues": [
            {
                "queue_name": "dummy",
                "request_schema": {"type": "object"}
            }
        ]
    }
}


class DummyService(object):
    def __init__(self):
        self.value = None
        self.value_set = Event()

        apis = [
            ServerAPI("api1", "desc1", [
                ArgParameter("p1", "d1", str),
                ArgParameter("p2", "d2", int),
                KeywordParameter("k3", "d3", bool)
            ], self.api1),
            ServerAPI("api2", "desc2", [], self.api2),
        ]
        self.rpc_server = RPCServer("name", "desc", apis, self)

    def api1(self, p1, p2, k3):
        if type(p1) != str or type(p2) != int or type(k3) != bool:
            self.value = None
        else:
            self.value = "{}{}{}".format(p1, p2, k3)
        self.value_set.set()

    def api2(self):
        self.value = "API2"
        self.value_set.set()

    def get_service_queue_name(self, path):
        return path

    def start(self):
        self.rpc_server.start()

    def stop(self):
        self.rpc_server.stop()


class TestRPC(object):
    @classmethod
    def setup_class(cls):
        os.environ["USE_FAKE_REDIS"] = "TRUE"
        cls.service_manager = ServiceManager(None)
        cls.service_manager.start_services(["messaging"])

    @classmethod
    def teardown_class(cls):
        del os.environ["USE_FAKE_REDIS"]
        cls.service_manager.stop()

    def setup_method(self):
        self.service = DummyService()
        self.service.start()

    def teardown_method(self):
        self.service.stop()

    def test_server_function_invoke(self):
        info = self.service.rpc_server.info_message
        client = RPCClient(info)
        client.start()

        client.apis["api1"]("hello", 5, k3=False)

        self.service.value_set.wait()
        assert self.service.value == "hello5False"

    def test_several_functions_invoke(self):
        info = self.service.rpc_server.info_message
        client = RPCClient(info)
        client.start()

        api1 = client.apis["api1"]
        api2 = client.apis["api2"]

        for i in range(50):
            api1("iter", i, k3=i % 2 == 0)
            self.service.value_set.wait()
            assert self.service.value == "iter{}{}".format(i, i % 2 == 0)
            self.service.value_set.clear()

            api2()
            self.service.value_set.wait()
            assert self.service.value == "API2"
            self.service.value_set.clear()
