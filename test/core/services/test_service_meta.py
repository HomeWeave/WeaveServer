from threading import Event, Thread

from app.core.messaging import Receiver, Sender
from app.core.services import EventDrivenService, Capability
from app.core.services import BaseService, BackgroundThreadServiceStart
from app.services.messaging import MessageService


CONFIG = {
    "redis_config": {
        "USE_FAKE_REDIS": True
    },
    "queues": {
        "system_queues": [
            {
                "queue_name": "_system/dynamic-queues/create",
                "request_schema": {
                    "type": "object",
                    "properties": {
                        "queue_name": {"type": "string"},
                        "queue_type": {
                            "type": "string",
                            "enum": ["redis", "sticky", "keyedsticky"]
                        },
                        "request_schema": {"type": "object"}
                    },
                    "required": ["queue_name", "request_schema"]
                }
            }
        ]
    }
}


class Service(EventDrivenService, BackgroundThreadServiceStart, BaseService):
    def on_service_start(self, *args, **kwargs):
        params = {
            "arg1": {"type": "string"}
        }
        capability = Capability("test", "test", params)
        self.express_capability(capability, self.handle)

    def get_component_name(self):
        return "test"

    def handle(self, arg1):
        self.value = arg1


class TestEventDrivenService(object):
    @classmethod
    def setup_class(cls):
        event = Event()
        cls.message_service = MessageService(CONFIG)
        cls.message_service.notify_start = lambda: event.set()
        cls.message_service_thread = Thread(
            target=cls.message_service.on_service_start)
        cls.message_service_thread.start()
        event.wait()

    @classmethod
    def teardown_class(cls):
        cls.message_service.on_service_stop()
        cls.message_service_thread.join()

    def setup_method(self):
        self.service = Service()
        self.service.on_service_start()

    def teardown_method(self):
        self.service.on_service_stop()

    def test_express_simple_capability_with_bad_schema(self):
        receiver = Receiver("/services/test/capabilities")
        receiver.start()
        obj = receiver.receive()

        assert len(obj.task) == 1
        value = next(iter(obj.task.values()))
        qid = value.pop("id")
        assert value == {
            "name": "test",
            "description": "test",
            "params": {"arg1": {"type": "string"}},
        }
