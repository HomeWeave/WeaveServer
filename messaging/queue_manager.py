import logging
from threading import RLock

from jsonschema import Draft4Validator, SchemaError

from weavelib.exceptions import ObjectNotFound, ObjectAlreadyExists
from weavelib.exceptions import ObjectClosed, SchemaValidationFailed
from weavelib.exceptions import InternalError, BadArguments

from .queues import FIFOQueue, SessionizedQueue, Multicast


logger = logging.getLogger(__name__)


class ChannelInfo(object):
    def __init__(self, channel_name, request_schema, response_schema,
                 authorizers=None):
        try:
            Draft4Validator.check_schema(request_schema)
        except SchemaError:
            raise SchemaValidationFailed(request_schema)
        try:
            Draft4Validator.check_schema(response_schema)
        except SchemaError:
            raise SchemaValidationFailed(response_schema)

        self.channel_name = channel_name
        self.request_schema = request_schema
        self.response_schema = response_schema
        self.authorizers = authorizers or {}

    def create_channel(self):
        raise NotImplementedError


class QueueInfo(ChannelInfo):
    def __init__(self, queue_name, request_schema, response_schema, queue_type,
                 authorizers=None):
        super(QueueInfo, self).__init__(queue_name, request_schema,
                                        response_schema,
                                        authorizers=authorizers)
        channel_map = {"fifo": FIFOQueue, "sessionized": SessionizedQueue}
        self.queue_cls = channel_map.get(queue_type)
        if not self.queue_cls:
            raise BadArguments(queue_type)

    def create_channel(self):
        return self.queue_cls(self)


class MulticastInfo(ChannelInfo):
    def __init__(self, multicast_name, request_schema, response_schema,
                 authorizers=None):
        super().__init__(multicast_name, request_schema, response_schema,
                         authorizers=authorizers)

    def create_channel(self):
        return Multicast(self)


class ChannelRegistry(object):
    def __init__(self):
        self.channel_map = {}
        self.channel_map_lock = RLock()
        self.active = True

    def create_queue(self, queue_name, request_schema, response_schema,
                     queue_type, authorizers=None):
        queue_info = QueueInfo(queue_name, request_schema, response_schema,
                               queue_type, authorizers)

        with self.channel_map_lock:
            if not self.active:
                raise ObjectClosed("Server shutting down.")

            if queue_info.channel_name in self.channel_map:
                raise ObjectAlreadyExists(queue_info.channel_name)

            queue = queue_info.create_channel()
            self.channel_map[queue_info.channel_name] = queue

        if not queue.connect():
            raise InternalError("Can't connect to queue: " + queue_name)

        logger.info("Created queue: %s", queue_name)
        return queue

    def create_multicast(self, multicast_name, request_schema, response_schema,
                         authorizers=None):
        multicast_info = MulticastInfo(multicast_name, request_schema,
                                       response_schema, authorizers)

        with self.channel_map_lock:
            if not self.active:
                raise ObjectClosed("Server shutting down.")

            if multicast_name in self.channel_map:
                raise ObjectAlreadyExists(multicast_name)

            multicast = multicast_info.create_channel()
            self.channel_map[multicast_name] = multicast

        if not multicast.connect():
            raise InternalError("Can't connect to multicast: " + multicast_name)

        logger.info("Created multicast: %s", multicast_name)
        return multicast

    def get_channel(self, channel_name):
        # TODO: Change to reader-writer lock.
        with self.channel_map_lock:
            try:
                return self.channel_map[channel_name]
            except KeyError:
                raise ObjectNotFound(channel_name)

    def shutdown(self):
        with self.channel_map_lock:
            self.active = False
            for channel in self.channel_map.values():
                channel.disconnect()
