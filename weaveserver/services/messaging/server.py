import json
import logging
import os
import time
from collections import defaultdict
from queue import Queue
from socketserver import ThreadingTCPServer, StreamRequestHandler
from threading import Condition, RLock
from uuid import uuid4

from jsonschema import validate, ValidationError, SchemaError
from redis import Redis, ConnectionError as RedisConnectionError

from weavelib.messaging import read_message, serialize_message, Message
from weavelib.messaging import QueueAlreadyExists, AuthenticationFailed
from weavelib.messaging import SchemaValidationFailed, BadOperation
from weavelib.messaging import RequiredFieldsMissing, InternalMessagingError
from weavelib.messaging import MessagingException, QueueNotFound
from weavelib.services import BaseService, BackgroundThreadServiceStart


logger = logging.getLogger(__name__)


def get_required_field(headers, key):
    if key not in headers:
        raise RequiredFieldsMissing("'{}' is required.".format(key))
    return headers[key]


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

    def connect(self):
        return True

    def disconnect(self):
        return True

    def validate_schema(self, msg):
        validate(msg, self.queue_info["request_schema"])

    def check_auth(self, task, headers):
        if not self.queue_info.get("force_auth"):
            return

        if not headers.get("AUTH"):
            raise AuthenticationFailed("Invalid AUTH header.")

        if headers["AUTH"].get("type") == "SYSTEM":
            return

        appid = headers["AUTH"]["appid"]

        if self.queue_info.get("authorization") and\
                appid not in self.queue_info["auth_whitelist"]:
            raise AuthenticationFailed("Unauthorized.")

    def pack_message(self, task, headers):
        reqd_headers = {"AUTH"}
        return {
            "task": task,
            "headers": {x: headers[x] for x in reqd_headers if x in headers}
        }

    def unpack_message(self, obj):
        return obj["task"], obj["headers"]

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
        self.check_auth(task, headers)
        obj = self.pack_message(task, headers)
        self.get_connection().lpush(self.redis_queue, json.dumps(obj))
        return True

    def dequeue(self, headers):
        self.check_auth(None, headers)
        timeout = int(headers.get("TIMEOUT", "0"))
        data = self.get_connection().brpop(self.redis_queue, timeout=timeout)
        if data:
            obj = json.loads(data[1])
            return self.unpack_message(obj)
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
            logger.exception("Unable to connect to real Redis.")
            return False
        return True

    def get_connection(self):
        if self.redis is None:
            raise RedisConnectionError()
        return self.redis


class SessionizedQueue(BaseQueue):
    def __init__(self, queue_info, queue_name, *args):
        super().__init__(queue_info)
        self.requestor_version_map = defaultdict(int)
        self.latest_version = 1
        self.messages = []
        self.condition = Condition()

    def enqueue(self, task, headers):
        cookie = get_required_field(headers, "COOKIE")
        self.validate_schema(task)
        self.check_auth(task, headers)

        obj = self.pack_message(task, headers)
        obj["cookie"] = cookie
        obj["time"] = time.time()

        with self.condition:
            self.latest_version += 1
            obj["version"] = self.latest_version
            self.messages.append(obj)
            self.condition.notify_all()

    def dequeue(self, headers):
        requestor_id = get_required_field(headers, "COOKIE")
        self.check_auth(None, headers)

        dequeue_result = []

        def test_dequeue():
            cur_version = self.requestor_version_map[requestor_id]
            for msg in self.messages:
                if msg["version"] <= cur_version:
                    continue
                if msg["cookie"] == requestor_id:
                    self.requestor_version_map[requestor_id] = msg["version"]
                    dequeue_result.append(self.unpack_message(msg))
                    return True
            return False

        with self.condition:
            self.condition.wait_for(test_dequeue)
            return dequeue_result[0]


class FIFOQueue(BaseQueue):
    def __init__(self, queue_info, *args, **kwargs):
        super().__init__(queue_info)
        self.queue = []
        self.condition = Condition()
        self.requestors = []

    def enqueue(self, task, headers):
        self.validate_schema(task)
        self.check_auth(task, headers)

        with self.condition:
            self.queue.append(self.pack_message(task, headers))
            self.condition.notify_all()

    def dequeue(self, headers):
        self.check_auth(None, headers)
        requestor_id = headers["SESS"]

        self.requestors.append(requestor_id)

        def can_dequeue():
            if not self.queue:
                return False

            if self.requestors[0] == requestor_id:
                return True
            return False

        with self.condition:
            self.condition.wait_for(can_dequeue)
            self.requestors.pop(0)
            return self.unpack_message(self.queue.pop(0))


class StickyQueue(BaseQueue):
    def __init__(self, queue_info, *args, **kwargs):
        super().__init__(queue_info)
        self.sticky_message = None
        self.requestors = set()
        self.requestor_lock = RLock()
        self.condition = Condition(self.requestor_lock)

    def enqueue(self, task, headers):
        self.validate_schema(task)
        self.check_auth(task, headers)
        with self.condition:
            self.sticky_message = self.pack_message(task, headers)
            self.requestors = set()
            self.condition.notify_all()

    def dequeue(self, headers):
        requestor_id = headers["SESS"]
        self.check_auth(None, headers)

        def can_dequeue():
            has_msg = self.sticky_message is not None
            new_requestor = requestor_id not in self.requestors
            return has_msg and new_requestor

        with self.condition:
            self.condition.wait_for(can_dequeue)
            self.requestors.add(requestor_id)
            return self.unpack_message(self.sticky_message)


class KeyedStickyQueue(BaseQueue):
    def __init__(self, queue_info, *args, **kwargs):
        super().__init__(queue_info)
        self.sticky_map = {}
        self.sticky_map_version = 1
        self.requestor_map = defaultdict(int)
        self.condition = Condition()

    def enqueue(self, task, headers):
        # Sticky Map doesn't support AUTH.
        key = get_required_field(headers, "KEY")

        self.validate_schema(task)
        with self.condition:
            self.sticky_map[key] = task
            self.sticky_map_version += 1
            self.condition.notify_all()

    def dequeue(self, headers):
        # Sticky Map doesn't support AUTH.
        requestor_id = headers["SESS"]

        def can_dequeue():
            return self.sticky_map_version != self.requestor_map[requestor_id]

        with self.condition:
            self.condition.wait_for(can_dequeue)
            self.requestor_map[requestor_id] = self.sticky_map_version
            return self.sticky_map, {}


class MessageHandler(StreamRequestHandler):
    def handle(self):
        sess = str(uuid4())
        app_info = None
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


class MessageServer(ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, service, port, redis_config, apps_auth):
        super().__init__(("", port), MessageHandler)
        self.service = service
        self.sent_start_notification = False
        self.queue_map = {}
        self.queue_map_lock = RLock()
        self.listener_map = {}
        self.sticky_messages = {}
        self.clients = {}
        self.redis_config = redis_config
        self.apps_auth = apps_auth

    def create_queue(self, queue_info, headers):
        try:
            schema = queue_info["request_schema"]
            if not isinstance(schema, dict):
                raise SchemaValidationFailed(json.dumps(schema))
            validate({}, schema)
        except KeyError:
            raise SchemaValidationFailed("'request_schema' required.")
        except SchemaError:
            raise SchemaValidationFailed(json.dumps(schema))
        except ValidationError:
            pass

        queue_types = {
            "redis": RedisQueue,
            "fifo": FIFOQueue,
            "sticky": StickyQueue,
            "keyedsticky": KeyedStickyQueue,
            "sessionized": SessionizedQueue
        }
        queue_name = queue_info["queue_name"]

        creator_id = headers["AUTH"]["appid"]
        queue_info.setdefault("auth_whitelist", set()).add(creator_id)

        cls = queue_types[queue_info.get("queue_type", "redis")]
        queue = cls(queue_info, queue_name, self.redis_config)
        self.queue_map[queue_name] = queue
        logger.info("Connecting to %s", queue)
        return queue

    def handle_message(self, msg):
        self.preprocess(msg)
        if msg.operation == "dequeue":
            task, headers = self.handle_dequeue(msg)
            msg = Message("inform", task)
            msg.headers.update(headers)
            return serialize_message(msg)
        elif msg.operation == "enqueue":
            self.handle_enqueue(msg)
            msg = Message("result")
            msg.headers["RES"] = "OK"
            return serialize_message(msg)
        elif msg.operation == "create":
            queue_name = self.handle_create(msg)
            msg = Message("result")
            msg.headers["RES"] = "OK"
            msg.headers["Q"] = queue_name
            return serialize_message(msg)
        else:
            raise BadOperation(msg.operation)

    def handle_enqueue(self, msg):
        if msg.task is None:
            raise RequiredFieldsMissing("Task is required for enqueue.")
        queue_name = get_required_field(msg.headers, "Q")
        try:
            queue = self.queue_map[queue_name]
        except KeyError:
            raise QueueNotFound(queue_name)
        try:
            queue.enqueue(msg.task, msg.headers)
        except ValidationError:
            msg = "Schema: {}, on instance: {}, for queue: {}".format(
                    queue.queue_info["request_schema"], msg.task, queue)
            raise SchemaValidationFailed(msg)
        except RedisConnectionError:
            logger.exception("Failed to talk to Redis.")
            raise InternalMessagingError()

    def handle_dequeue(self, msg):
        queue_name = get_required_field(msg.headers, "Q")
        try:
            queue = self.queue_map[queue_name]
        except KeyError:
            raise QueueNotFound(queue_name)
        try:
            return queue.dequeue(msg.headers)
        except RedisConnectionError:
            logger.exception("failed to talk to Redis.")
            raise InternalMessagingError

    def handle_create(self, msg):
        if msg.task is None:
            raise RequiredFieldsMissing("QueueInfo is required for create.")

        app_info = get_required_field(msg.headers, "AUTH")
        if app_info is None:
            raise AuthenticationFailed("AUTH header missing/invalid.")

        if app_info.get("type") == "SYSTEM":
            queue_name = os.path.join("/", msg.task["queue_name"].lstrip("/"))
        else:
            queue_name = os.path.join("/plugins",
                                      app_info["package"].strip("/"),
                                      app_info["appid"],
                                      msg.task["queue_name"].lstrip("/"))

        msg.task["queue_name"] = queue_name

        if msg.task.get("queue_type") == "keyedsticky" and \
                msg.task.get("force_auth"):
            raise BadOperation("KeyedSticky can not force AUTH.")

        with self.queue_map_lock:
            if queue_name in self.queue_map:
                raise QueueAlreadyExists(queue_name)
            queue = self.create_queue(msg.task, msg.headers)

        if not queue.connect():
            raise InternalMessagingError("Cant connect: " + queue_name)

        self.queue_map[msg.task["queue_name"]] = queue

        logger.info("Connected: %s", queue)

        return queue_name

    def preprocess(self, msg):
        if "AUTH" in msg.headers:
            msg.headers["AUTH"] = self.apps_auth.get(msg.headers["AUTH"])

    def run(self):
        for queue in self.queue_map.values():
            if not queue.connect():
                logger.error("Unable to connect to: %s", queue)
                return
        self.serve_forever()

    def service_actions(self):
        if not self.sent_start_notification:
            self.service.notify_start()
            self.sent_start_notification = True

    def shutdown(self):
        for _, queue in self.queue_map.items():
            queue.disconnect()
        super().shutdown()
        super().server_close()


class MessageService(BackgroundThreadServiceStart, BaseService):
    PORT = 11023

    def __init__(self, token, config):
        super().__init__(token)
        self.redis_config = config["redis_config"]
        self.apps_auth = config["apps"]

    def get_component_name(self):
        return "weaveserver.services.messaging"

    def before_service_start(self):
        """Need to override to prevent rpc_client connecting."""

    def on_service_start(self, *args, **kwargs):
        self.message_server = MessageServer(self, self.PORT, self.redis_config,
                                            self.apps_auth)
        self.message_server.run()

    def on_service_stop(self):
        self.message_server.shutdown()
