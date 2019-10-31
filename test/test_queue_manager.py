import pytest

from weavelib.exceptions import SchemaValidationFailed, ObjectAlreadyExists
from weavelib.exceptions import ObjectNotFound, InternalError, ObjectClosed
from weavelib.exceptions import BadArguments

from messaging.application_registry import ApplicationRegistry, Plugin
from messaging.queue_manager import ChannelRegistry
from messaging.queues import SessionizedQueue, RoundRobinQueue


class TestChannelRegistry(object):
    @pytest.mark.parametrize("queue_type,expected_cls",
                             [("sessionized", SessionizedQueue),
                              ("fifo", RoundRobinQueue)])
    def test_create_queue_simple(self, queue_type, expected_cls):
        test_app = Plugin("test", "test", "test-token")
        apps = ApplicationRegistry()
        registry = ChannelRegistry(apps)
        queue = registry.create_queue("queue_name", test_app, {}, {},
                                      queue_type)

        assert isinstance(queue, expected_cls)
        assert registry.get_channel("queue_name") is queue

    def test_create_queue_bad_queue_type(self):
        test_app = Plugin("test", "test", "test-token")
        apps = ApplicationRegistry()
        registry = ChannelRegistry(apps)
        with pytest.raises(BadArguments):
            registry.create_queue("queue_name", test_app, {}, {}, "bad-type")

    def test_create_queue_bad_schema(self):
        test_app = Plugin("test", "test", "test-token")
        apps = ApplicationRegistry()
        registry = ChannelRegistry(apps)
        with pytest.raises(SchemaValidationFailed):
            registry.create_queue("queue_name", test_app, "test", {}, "fifo")

        with pytest.raises(SchemaValidationFailed):
            registry.create_queue("queue_name", test_app, {}, "test", "fifo")

    def test_queue_already_exists(self):
        test_app = Plugin("test", "test", "test-token")
        apps = ApplicationRegistry()
        registry = ChannelRegistry(apps)
        queue = registry.create_queue("queue_name", test_app, {}, {},
                                      "sessionized")
        assert isinstance(queue, SessionizedQueue)

        with pytest.raises(ObjectAlreadyExists):
            registry.create_queue("queue_name", test_app, {}, {}, "fifo")

    def test_get_queue_invalid(self):
        test_app = Plugin("test", "test", "test-token")
        apps = ApplicationRegistry()
        registry = ChannelRegistry(apps)
        with pytest.raises(ObjectNotFound):
            registry.get_channel("test_queue")

    def test_queue_connect_fail(self):
        backup = RoundRobinQueue.connect
        RoundRobinQueue.connect = lambda self: False

        test_app = Plugin("test", "test", "test-token")
        apps = ApplicationRegistry()
        registry = ChannelRegistry(apps)
        with pytest.raises(InternalError):
            registry.create_queue("queue_name", test_app, {}, {}, "fifo")

        RoundRobinQueue.connect = backup

    def test_shutdown(self):
        test_app = Plugin("test", "test", "test-token")
        apps = ApplicationRegistry()
        registry = ChannelRegistry(apps)

        queue1 = registry.create_queue("queue1", test_app, {}, {}, "fifo")
        queue2 = registry.create_queue("queue2", test_app, {}, {},
                                       "sessionized")

        flag = []
        def disconnect_fn():
            flag.append(None)

        queue1.disconnect = disconnect_fn
        queue2.disconnect = disconnect_fn

        registry.shutdown()

        assert len(flag) == 2

        with pytest.raises(ObjectClosed):
            registry.create_queue("queue3", test_app, {}, {}, "fifo")
