from threading import RLock

from jsonschema import Draft4Validator, SchemaError

from weavelib.exceptions import ObjectNotFound, ObjectAlreadyExists
from weavelib.exceptions import SchemaValidationFailed, InternalError

from .queues import FIFOQueue, SessionizedQueue


class QueueInfo(object):
    def __init__(self, queue_name, request_schema, response_schema,
                 is_sessionized=False, force_auth=False):
        try:
            Draft4Validator.check_schema(request_schema)
        except SchemaError:
            raise SchemaValidationFailed(request_schema)
        try:
            Draft4Validator.check_schema(response_schema)
        except SchemaError:
            raise SchemaValidationFailed(response_schema)

        self.queue_name = queue_name
        self.request_schema = request_schema
        self.response_schema = response_schema
        self.queue_cls = FIFOQueue if not is_sessionized else SessionizedQueue
        self.force_auth = force_auth

    def create_queue(self):
        return self.queue_cls(self)


class QueueRegistry(object):
    def __init__(self):
        self.queue_map = {}
        self.queue_map_lock = RLock()

    def create_queue(self, queue_name, request_schema, response_schema,
                     is_sessionized=False, force_auth=False):
        queue_info = QueueInfo(queue_name, request_schema, response_schema,
                               is_sessionized, force_auth)

        with self.queue_map_lock:
            if queue_info.queue_name in self.queue_map:
                raise ObjectAlreadyExists(queue_info.queue_name)
            queue = queue_info.create_queue()
            self.queue_map[queue_info.queue_name] = queue

        if not queue.connect():
            raise InternalError("Can't connect to queue: " + queue_name)

        return queue

    def get_queue(self, queue_name):
        # TODO: Change to reader-writer lock.
        with self.queue_map_lock:
            try:
                return self.queue_map[queue_name]
            except KeyError:
                raise ObjectNotFound(queue_name)
