import json
import logging
import os
from collections import defaultdict
from copy import deepcopy
from queue import Queue
from socketserver import ThreadingTCPServer, StreamRequestHandler
from threading import Condition, RLock, Thread
from uuid import uuid4

from jsonschema import validate, ValidationError
from redis import Redis, ConnectionError as RedisConnectionError

from app.core.messaging import read_message, serialize_message, Message
from app.core.messaging import Receiver
from app.core.messaging import SchemaValidationFailed, BadOperation
from app.core.messaging import RequiredFieldsMissing, InternalMessagingError
from app.core.messaging import MessagingException, QueueNotFound
from app.core.services import BaseService, BackgroundProcessServiceStart
from .system_queues import SYSTEM_QUEUES


logger = logging.getLogger(__name__)


class FakeRedis(object):
    """ Fake Redis. Use for testing only. Uses queue.Queue."""
    def __init__(self):
        self.queue_map = defaultdict(Queue)

    def lpush(self, queue, obj):
        self.queue_map[queue].put(obj)

    def brpop(self, queue, timeout=0):
        timeout = timeout if timeout else None
        return queue, self.queue_map[queue].get(timeout=timeout)


class BaseQueue(object):
    def __init__(self, queue_info):
        self.queue_info = queue_info

    def enqueue(self, task, headers):
        pass

    def dequeue(self, requestor_id):
        pass

    def connect(self):
        return True

    def disconnect(self):
        return True

    def validate_schema(self, msg):
        validate(msg, self.queue_info["request_schema"])

    def __repr__(self):
        return (self.__class__.__name__ +
                "({})".format(self.queue_info["queue_name"]))


class RedisQueue(BaseQueue):
    REDIS_PORT = 6379

    def __init__(self, queue_info, queue_name, redis_config):
        super().__init__(queue_info)
        self.queue_name = queue_name
        self.redis_queue = "queue-" + queue_name
        self.redis_config = {
            "host": redis_config.get("REDIS_HOST") or "localhost",
            "port": int(redis_config.get("REDIS_PORT") or self.REDIS_PORT),
            "db": int(redis_config.get("REDIS_DB") or 0),
            "password": redis_config.get("REDIS_PASSWD")
        }
        self.use_fake = redis_config.get("USE_FAKE_REDIS", None)
        self.redis = None

    def enqueue(self, task, headers):
        self.validate_schema(task)
        self.get_connection().lpush(self.redis_queue, json.dumps(task))
        return True

    def dequeue(self, requestor_id, timeout=0):
        data = self.get_connection().brpop(self.redis_queue, timeout=timeout)
        if data:
            task = json.loads(data[1])
            return task
        logger.warning("Redis dequeue returned nothing: %s", data)
        return None

    def connect(self):
        if self.use_fake:
            self.redis = FakeRedis()
            return True

        try:
            self.redis = Redis(**self.redis_config)
            self.redis.info()
        except RedisConnectionError:
            logger.exception("Not in test cases.")
            return False
        return True

    def get_connection(self):
        if self.redis is None:
            raise RedisConnectionError()
        return self.redis


class StickyQueue(BaseQueue):
    def __init__(self, queue_info, *args, **kwargs):
        super().__init__(queue_info)
        self.sticky_message = None
        self.requestors = set()
        self.requestor_lock = RLock()
        self.condition = Condition(self.requestor_lock)
        self.active = False

    def enqueue(self, task, headers):
        self.validate_schema(task)
        with self.condition:
            self.sticky_message = task
            self.requestors = set()
            self.condition.notify_all()

    def dequeue(self, requestor_id):
        def can_dequeue():
            if not self.active:
                return True
            has_msg = self.sticky_message is not None
            new_requestor = requestor_id not in self.requestors
            return has_msg and new_requestor

        with self.condition:
            self.condition.wait_for(can_dequeue)
            if self.active:
                self.requestors.add(requestor_id)
            else:
                return None
            return self.sticky_message

    def connect(self):
        self.active = True
        return True

    def disconnect(self):
        with self.condition:
            self.active = False
            self.condition.notify_all()


class KeyedStickyQueue(BaseQueue):
    def __init__(self, queue_info, *args, **kwargs):
        super().__init__(queue_info)
        self.sticky_map = {}
        self.requestor_map = defaultdict(set)
        self.condition = Condition()
        self.active = False

    def enqueue(self, task, headers):
        try:
            key = headers["KEY"]
        except KeyError:
            raise RequiredFieldsMissing("Field ''KEY' is required.")

        self.validate_schema(task)
        with self.condition:
            self.sticky_map[key] = task
            self.condition.notify_all()

    def dequeue(self, requestor_id):
        def can_dequeue():
            # Return if no longer active.
            if not self.active:
                return True
            # If a new requestor, always send something, including empty {}
            if requestor_id not in self.requestor_map:
                return True
            sent_keys = self.requestor_map[requestor_id]
            new_keys = set(self.sticky_map.keys())
            keys_to_send = new_keys - sent_keys
            return keys_to_send

        with self.condition:
            self.condition.wait_for(can_dequeue)
            if self.active:
                self.requestor_map[requestor_id] |= self.sticky_map.keys()
                return self.sticky_map
            else:
                return None

    def connect(self):
        self.active = True
        return True

    def disconnect(self):
        with self.condition:
            self.active = False
            self.condition.notify_all()

class MessageHandler(StreamRequestHandler):
    def handle(self):
        sess_id = str(uuid4())
        sess = str(uuid4())
        while True:
            try:
                msg = read_message(self.rfile)
                msg.headers["SESS"] = sess
                self.reply(self.server.handle_message(msg))
            except MessagingException as e:
                self.reply(serialize_message(e.to_msg()))
                continue
            except IOError:
                break

    def reply(self, msg):
        self.wfile.write((msg + "\n").encode())
        self.wfile.flush()


class TemplateQueueCreator(Receiver):
    def __init__(self, message_server, app_queue_infos):
        self.message_server = message_server
        self.app_queue_infos = app_queue_infos
        self.services = set()
        super().__init__("_system/app-queues/create")

    def on_message(self, service_name):
        logger.info(service_name)
        if service_name not in self.services:
            for queue_info in self.app_queue_infos:
                self.create_dynamic_queue(service_name, queue_info)
                self.services.add(service_name)

    def create_dynamic_queue(self, service_name, queue_info):
        queue_info = deepcopy(queue_info)
        rel_name = queue_info["queue_name"].lstrip('/')
        new_queue = os.path.join("/", service_name, rel_name)
        queue_info["queue_name"] = new_queue
        queue = self.message_server.create_queue(queue_info)
        queue.connect()

    def stop(self):
        super().stop()


class MessageServer(ThreadingTCPServer):
    allow_reuse_address = True

    def __init__(self, service, port, redis_config, queue_config):
        super().__init__(("", port), MessageHandler)
        self.service = service
        self.sent_start_notification = False
        self.queue_map = {}
        self.listener_map = {}
        self.sticky_messages = {}
        self.clients = {}
        self.redis_config = redis_config

        app_queue_config = queue_config["default_app_queues"]
        self.app_queue_creator = TemplateQueueCreator(self, app_queue_config)
        self.app_queue_thread = Thread(target=self.app_queue_creator.run,
                                       name="DynQueueThread")
        for queue_info in SYSTEM_QUEUES:
            self.create_queue(queue_info)

        for queue_info in queue_config["custom_queues"]:
            self.create_queue(queue_info)

    def create_queue(self, queue_info):
        queue_types = {
            "redis": RedisQueue,
            "sticky": StickyQueue,
            "keyedsticky": KeyedStickyQueue,
        }
        queue_name = queue_info["queue_name"]
        cls = queue_types[queue_info.get("queue_type", "redis")]
        queue = cls(queue_info, queue_name, self.redis_config)
        self.queue_map[queue_name] = queue
        logger.info("Connecting to %s", queue)
        return queue

    def handle_message(self, msg):
        if msg.operation == "dequeue":
            item = self.handle_dequeue(msg)
            return serialize_message(Message("inform", item))
        elif msg.operation == "enqueue":
            self.handle_enqueue(msg)
            msg = Message("result")
            msg.headers["RES"] = "OK"
            return serialize_message(msg)
        else:
            raise BadOperation(msg.operation)

    def handle_enqueue(self, msg):
        if msg.task is None:
            raise RequiredFieldsMissing("Task is required for enqueue.")
        try:
            queue_name = msg.headers["Q"]
        except KeyError:
            raise RequiredFieldsMissing("Field 'Q' is required for enqueue.")

        try:
            queue = self.queue_map[queue_name]
            queue.enqueue(msg.task, msg.headers)
        except KeyError:
            raise QueueNotFound(queue_name)
        except ValidationError:
            raise SchemaValidationFailed()
        except RedisConnectionError:
            logger.exception("Failed to talk to Redis.")
            raise InternalMessagingError()

    def handle_dequeue(self, msg):
        try:
            queue_name = msg.headers["Q"]
        except KeyError:
            raise RequiredFieldsMissing("Field 'Q' is required for dequeue.")

        requestor_id = msg.headers["SESS"]
        try:
            queue = self.queue_map[queue_name]
            return queue.dequeue(requestor_id)
        except KeyError:
            raise QueueNotFound(queue_name)
        except RedisConnectionError:
            logger.exception("failed to talk to Redis.")
            raise InternalMessagingError

    def run(self):
        for queue in self.queue_map.values():
            if not queue.connect():
                logger.error("Unable to connect to: %s", queue)
                return
        self.app_queue_creator.start()
        self.app_queue_thread.start()
        self.serve_forever()

    def service_actions(self):
        if not self.sent_start_notification:
            self.service.notify_start()
            self.sent_start_notification = True

    def shutdown(self):
        for _, queue in self.queue_map.items():
            queue.disconnect()
        self.app_queue_creator.stop()
        self.app_queue_thread.join()
        super().shutdown()
        super().server_close()


class MessageService(BackgroundProcessServiceStart, BaseService):
    PORT = 11023

    def __init__(self, config):
        self.redis_config = config["redis_config"]
        self.queues = config["queues"]
        super().__init__()

    def get_component_name(self):
        return "messaging"

    def on_service_start(self, *args, **kwargs):
        self.message_server = MessageServer(self, self.PORT, self.redis_config,
                                            self.queues)
        self.message_server.run()

    def on_service_stop(self):
        self.message_server.shutdown()
