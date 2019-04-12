import pytest

from weavelib.exceptions import SchemaValidationFailed

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
