import pytest

from weavelib.exceptions import SchemaValidationFailed, ObjectAlreadyExists
from weavelib.exceptions import ObjectNotFound, InternalError

from messaging.queue_manager import QueueRegistry
from messaging.queues import SessionizedQueue, FIFOQueue


class TestQueueRegistry(object):
    @pytest.mark.parametrize("is_sessionized,expected_cls",
                             [(True, SessionizedQueue),
                              (False, FIFOQueue)])
    def test_create_queue_simple(self, is_sessionized, expected_cls):
        registry = QueueRegistry()
        queue = registry.create_queue("queue_name", {}, {}, is_sessionized)

        assert isinstance(queue, expected_cls)
        assert registry.get_queue("queue_name") is queue

    def test_create_queue_bad_schema(self):
        registry = QueueRegistry()
        with pytest.raises(SchemaValidationFailed):
            registry.create_queue("queue_name", "test", {})

        with pytest.raises(SchemaValidationFailed):
            registry.create_queue("queue_name", {}, "test")

    def test_queue_already_exists(self):
        registry = QueueRegistry()
        queue = registry.create_queue("queue_name", {}, {}, True)
        assert isinstance(queue, SessionizedQueue)

        with pytest.raises(ObjectAlreadyExists):
            registry.create_queue("queue_name", {}, {}, False)

    def test_get_queue_invalid(self):
        registry = QueueRegistry()
        with pytest.raises(ObjectNotFound):
            registry.get_queue("test_queue")

    def test_queue_connect_fail(self):
        backup = FIFOQueue.connect
        FIFOQueue.connect = lambda self: False

        registry = QueueRegistry()
        with pytest.raises(InternalError):
            registry.create_queue("queue_name", {}, {}, False)

        FIFOQueue.connect = backup
