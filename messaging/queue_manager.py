import logging
from threading import RLock

from jsonschema import Draft4Validator, SchemaError

from weavelib.exceptions import ObjectNotFound, ObjectAlreadyExists
from weavelib.exceptions import ObjectClosed, SchemaValidationFailed
from weavelib.exceptions import InternalError, BadArguments

from .queues import FIFOQueue, SessionizedQueue, Multicast


logger = logging.getLogger(__name__)


class ChannelInfo(object):
    def __init__(self, channel_name, owner_app, request_schema, response_schema,
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
        self.owner_app = owner_app

    def create_channel(self):
        raise NotImplementedError


class QueueInfo(ChannelInfo):
    def __init__(self, queue_name, owner_app, request_schema, response_schema,
                 queue_type, authorizers=None):
        super().__init__(queue_name, owner_app, request_schema, response_schema,
                         authorizers=authorizers)
        channel_map = {"fifo": FIFOQueue, "sessionized": SessionizedQueue}
        self.queue_cls = channel_map.get(queue_type)
        if not self.queue_cls:
            raise BadArguments(queue_type)

    def create_channel(self):
        return self.queue_cls(self)


class MulticastInfo(ChannelInfo):
    def __init__(self, multicast_name, owner_app, request_schema,
                 response_schema, authorizers=None):
        super().__init__(multicast_name, owner_app, request_schema,
                         response_schema, authorizers=authorizers)

    def create_channel(self):
        return Multicast(self)


class ChannelRegistry(object):
    def __init__(self, app_registry):
        self.channel_map = {}
        self.channel_map_lock = RLock()
        self.app_registry = app_registry
        self.active = True

    def create_queue(self, queue_name, owner_app, request_schema,
                     response_schema, queue_type, authorizers=None):
        queue_info = QueueInfo(queue_name, owner_app, request_schema,
                               response_schema, queue_type, authorizers)

        return self.create_channel_internal(queue_info)

    def create_multicast(self, multicast_name, owner_app, request_schema,
                         response_schema, authorizers=None):
        multicast_info = MulticastInfo(multicast_name, owner_app,
                                       request_schema, response_schema,
                                       authorizers)
        return self.create_channel_internal(multicast_info)

    def create_channel_internal(self, channel_info):
        with self.channel_map_lock:
            if not self.active:
                raise ObjectClosed("Server shutting down.")

            if channel_info.channel_name in self.channel_map:
                raise ObjectAlreadyExists(channel_info.channel_name)

            channel = channel_info.create_channel()
            self.channel_map[channel_info.channel_name] = channel

        if not channel.connect():
            raise InternalError("Can't connect to channel: " + str(channel))

        logger.info("Created channel: %s", channel)
        return channel

    def update_channel_schema(self, channel_name, request_schema,
                              response_schema):
        with self.channel_map_lock:
            try:
                channel_info = self.channel_map[channel_name].channel_info
            except KeyError:
                raise ObjectNotFound(channel_name)

        # TODO: This might need to be protected by a lock.
        channel_info.request_schema = request_schema
        channel_info.response_schema = response_schema
        logger.info(channel_info.request_schema)
        return True

    def remove_channel(self, channel_name):
        with self.channel_map_lock:
            try:
                channel = self.channel_map.pop(channel_name)
            except KeyError:
                raise ObjectNotFound(channel_name)
        channel.disconnect()
        return True

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
