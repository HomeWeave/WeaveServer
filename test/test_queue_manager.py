import pytest

from weavelib.exceptions import SchemaValidationFailed, ObjectAlreadyExists
from weavelib.exceptions import ObjectNotFound, InternalError, ObjectClosed
from weavelib.exceptions import BadArguments

from messaging.queue_manager import ChannelRegistry
from messaging.queues import SessionizedQueue, FIFOQueue


class TestChannelRegistry(object):
    @pytest.mark.parametrize("queue_type,expected_cls",
                             [("sessionized", SessionizedQueue),
                              ("fifo", FIFOQueue)])
    def test_create_queue_simple(self, queue_type, expected_cls):
        registry = ChannelRegistry()
        queue = registry.create_queue("queue_name", {}, {}, queue_type)

        assert isinstance(queue, expected_cls)
        assert registry.get_queue("queue_name") is queue

    def test_create_queue_bad_queue_type(self):
        registry = ChannelRegistry()
        with pytest.raises(BadArguments):
            registry.create_queue("queue_name", {}, {}, "bad-type")

    def test_create_queue_bad_schema(self):
        registry = ChannelRegistry()
        with pytest.raises(SchemaValidationFailed):
            registry.create_queue("queue_name", "test", {}, "fifo")

        with pytest.raises(SchemaValidationFailed):
            registry.create_queue("queue_name", {}, "test", "fifo")

    def test_queue_already_exists(self):
        registry = ChannelRegistry()
        queue = registry.create_queue("queue_name", {}, {}, "sessionized")
        assert isinstance(queue, SessionizedQueue)

        with pytest.raises(ObjectAlreadyExists):
            registry.create_queue("queue_name", {}, {}, "fifo")

    def test_get_queue_invalid(self):
        registry = ChannelRegistry()
        with pytest.raises(ObjectNotFound):
            registry.get_queue("test_queue")

    def test_queue_connect_fail(self):
        backup = FIFOQueue.connect
        FIFOQueue.connect = lambda self: False

        registry = ChannelRegistry()
        with pytest.raises(InternalError):
            registry.create_queue("queue_name", {}, {}, "fifo")

        FIFOQueue.connect = backup

    def test_shutdown(self):
        registry = ChannelRegistry()
        queue1 = registry.create_queue("queue1", {}, {}, "fifo")
        queue2 = registry.create_queue("queue2", {}, {}, "sessionized")

        flag = []
        def disconnect_fn():
            flag.append(None)

        queue1.disconnect = disconnect_fn
        queue2.disconnect = disconnect_fn

        registry.shutdown()

        assert len(flag) == 2

        with pytest.raises(ObjectClosed):
            registry.create_queue("queue3", {}, {}, "fifo")
