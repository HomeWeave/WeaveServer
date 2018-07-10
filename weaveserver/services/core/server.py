import json
import logging
import os
import time
from collections import defaultdict
from socketserver import ThreadingTCPServer, StreamRequestHandler
from threading import Condition, RLock
from uuid import uuid4

from jsonschema import validate, ValidationError, SchemaError

from weavelib.exceptions import WeaveException, ObjectNotFound, ObjectClosed
from weavelib.exceptions import ObjectAlreadyExists, AuthenticationFailed
from weavelib.exceptions import ProtocolError, BadOperation, InternalError
from weavelib.exceptions import SchemaValidationFailed
from weavelib.messaging import read_message, serialize_message, Message
from weavelib.messaging import exception_to_message


logger = logging.getLogger(__name__)


def get_required_field(headers, key):
    if key not in headers:
        raise ProtocolError("'{}' is required.".format(key))
    return headers[key]


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
                appid not in self.queue_info["authorization"]["auth_whitelist"]:
            raise AuthenticationFailed("Unauthorized.")

    def pack_message(self, task, headers):
        reqd = {"AUTH": json.dumps}
        headers = {x: f(headers[x]) for x, f in reqd.items() if x in headers}
        return {
            "task": task,
            "headers": headers
        }

    def unpack_message(self, obj):
        return obj["task"], obj["headers"]

    def __repr__(self):
        return (self.__class__.__name__ +
                "({})".format(self.queue_info["queue_name"]))


class SynchronousQueue(BaseQueue):
    REQUESTOR_ID_FIELD = "SESS"

    def __init__(self, queue_info):
        super().__init__(queue_info)
        self.condition = Condition()
        self.active = False

    def connect(self):
        self.active = True
        return True

    def disconnect(self):
        self.active = False
        with self.condition:
            self.condition.notify_all()

    def pack_attributes(self, task, headers):
        return {}

    def enqueue(self, task, headers):
        self.validate_schema(task)
        self.check_auth(task, headers)

        msg = self.pack_message(task, headers)
        msg.update(self.pack_attributes(task, headers))

        with self.condition:
            self.on_enqueue(msg)
            self.condition.notify_all()

    def before_dequeue(self, requestor_id):
        pass

    def dequeue(self, headers):
        requestor_id = get_required_field(headers, self.REQUESTOR_ID_FIELD)
        self.check_auth(None, headers)

        self.before_dequeue(requestor_id)

        with self.condition:
            while True:
                if not self.active:
                    raise ObjectClosed(self)

                condition_value = self.dequeue_condition(requestor_id)
                if not condition_value:
                    self.condition.wait()
                else:
                    msg = self.on_dequeue(requestor_id, condition_value)
                    return self.unpack_message(msg)


class SessionizedQueue(SynchronousQueue):
    REQUESTOR_ID_FIELD = "COOKIE"

    def __init__(self, queue_info):
        super().__init__(queue_info)
        self.requestor_version_map = defaultdict(int)
        self.latest_version = 1
        self.messages = []

    def pack_attributes(self,  task, headers):
        return {
            "cookie": get_required_field(headers, "COOKIE"),
            "time": time.time()
        }

    def on_enqueue(self, obj):
        self.latest_version += 1
        obj["version"] = self.latest_version
        self.messages.append(obj)

    def dequeue_condition(self, requestor_id):
        cur_version = self.requestor_version_map[requestor_id]
        for msg in self.messages:
            if msg["version"] <= cur_version:
                continue
            if msg["cookie"] == requestor_id:
                return msg
        return None

    def on_dequeue(self, requestor_id, condition_value):
        self.requestor_version_map[requestor_id] = condition_value["version"]
        return condition_value


class FIFOQueue(SynchronousQueue):
    def __init__(self, queue_info):
        super().__init__(queue_info)
        self.queue = []
        self.requestors = []

    def on_enqueue(self, obj):
        self.queue.append(obj)

    def dequeue_condition(self, requestor_id):
        return self.queue and self.requestors[0] == requestor_id

    def before_dequeue(self, requestor_id):
        self.requestors.append(requestor_id)

    def on_dequeue(self, requestor_id, condition_value):
        self.requestors.pop(0)
        return self.queue.pop(0)


class StickyQueue(SynchronousQueue):
    def __init__(self, queue_info):
        super().__init__(queue_info)
        self.sticky_message = None
        self.requestors = set()

    def on_enqueue(self, msg):
        self.sticky_message = msg
        self.requestors = set()

    def dequeue_condition(self, requestor_id):
        has_msg = self.sticky_message is not None
        new_requestor = requestor_id not in self.requestors
        return has_msg and new_requestor

    def on_dequeue(self, requestor_id, condition_value):
        self.requestors.add(requestor_id)
        return self.sticky_message


class KeyedStickyQueue(BaseQueue):
    def __init__(self, queue_info):
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
        while True:
            try:
                msg = read_message(self.rfile)
                msg.headers["SESS"] = sess
                self.reply(self.server.handle_message(msg))
            except WeaveException as e:
                self.reply(serialize_message(exception_to_message(e)))
                continue
            except IOError:
                break

    def reply(self, msg):
        self.wfile.write((msg + "\n").encode())
        self.wfile.flush()


class MessageServer(ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, port, apps_auth, notify_start):
        super().__init__(("", port), MessageHandler)
        self.notify_start = notify_start
        self.sent_start_notification = False
        self.queue_map = {}
        self.queue_map_lock = RLock()
        self.listener_map = {}
        self.sticky_messages = {}
        self.clients = {}
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
            "fifo": FIFOQueue,
            "sticky": StickyQueue,
            "keyedsticky": KeyedStickyQueue,
            "sessionized": SessionizedQueue
        }
        queue_name = queue_info["queue_name"]

        creator_id = headers["AUTH"]["appid"]
        queue_info.setdefault("auth_whitelist", set()).add(creator_id)

        cls = queue_types[queue_info.get("queue_type", "fifo")]
        queue = cls(queue_info)
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
            raise ProtocolError("Task is required for enqueue.")
        queue_name = get_required_field(msg.headers, "Q")
        try:
            queue = self.queue_map[queue_name]
        except KeyError:
            raise ObjectNotFound(queue_name)
        try:
            queue.enqueue(msg.task, msg.headers)
        except ValidationError:
            msg = "Schema: {}, on instance: {}, for queue: {}".format(
                    queue.queue_info["request_schema"], msg.task, queue)
            raise SchemaValidationFailed(msg)

    def handle_dequeue(self, msg):
        queue_name = get_required_field(msg.headers, "Q")
        try:
            queue = self.queue_map[queue_name]
        except KeyError:
            raise ObjectNotFound(queue_name)
        return queue.dequeue(msg.headers)

    def handle_create(self, msg):
        if msg.task is None:
            raise ProtocolError("QueueInfo is required for create.")

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
                raise ObjectAlreadyExists(queue_name)
            queue = self.create_queue(msg.task, msg.headers)

        if not queue.connect():
            raise InternalError("Cant connect: " + queue_name)

        self.queue_map[msg.task["queue_name"]] = queue

        logger.info("Connected: %s", queue)

        return queue_name

    def preprocess(self, msg):
        if "AUTH" in msg.headers:
            msg.headers["AUTH"] = self.apps_auth.get(msg.headers["AUTH"])

    def register_application(self, auth_info):
        self.apps_auth[auth_info["appid"]] = auth_info

    def run(self):
        for queue in self.queue_map.values():
            if not queue.connect():
                logger.error("Unable to connect to: %s", queue)
                return
        self.serve_forever()

    def service_actions(self):
        if not self.sent_start_notification:
            self.notify_start()
            self.sent_start_notification = True

    def shutdown(self):
        for _, queue in self.queue_map.items():
            queue.disconnect()
        super().shutdown()
        super().server_close()
