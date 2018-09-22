import json
import logging
import os
try:
    from queue import Queue
except ImportError:
    from Queue import Queue
import time
from collections import defaultdict
from socketserver import ThreadingTCPServer, StreamRequestHandler
from threading import RLock, Thread
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


def safe_close(obj):
    try:
        obj.close()
    except (IOError, OSError):
        pass


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
        self.active = False
        self.current_requestors = {}

    def connect(self):
        self.active = True
        return True

    def disconnect(self):
        self.active = False

    def pack_attributes(self, task, headers):
        return {}

    def enqueue(self, task, headers):
        self.validate_schema(task)
        self.check_auth(task, headers)

        msg = self.pack_message(task, headers)
        msg.update(self.pack_attributes(task, headers))

        self.on_enqueue(msg)

        for requestor, out in self.current_requestors.items():
            value = self.dequeue_condition(requestor)
            if value:
                msg = self.on_dequeue(requestor, value)
                out(self.unpack_message(msg))

    def on_enqueue(self, msg):
        raise NotImplementedError

    def before_dequeue(self, requestor_id):
        pass

    def dequeue_condition(self, requestor_id):
        raise NotImplementedError

    def on_dequeue(self, requestor_id, condition_value):
        raise NotImplementedError

    def dequeue(self, headers, out):
        requestor_id = get_required_field(headers, self.REQUESTOR_ID_FIELD)
        self.check_auth(None, headers)

        self.current_requestors[requestor_id] = out
        self.before_dequeue(requestor_id)

        condition_value = self.dequeue_condition(requestor_id)
        if condition_value:
            msg = self.on_dequeue(requestor_id, condition_value)
            out(self.unpack_message(msg))


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
        return self.queue and self.requestors and \
               self.requestors[0] == requestor_id

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
        self.requestor_map = {}

    def enqueue(self, task, headers):
        # Sticky Map doesn't support AUTH.
        key = get_required_field(headers, "KEY")

        self.validate_schema(task)
        self.sticky_map[key] = task
        self.sticky_map_version += 1

        for requestor_id, (version, out) in self.requestor_map.items():
            if self.sticky_map_version != version:
                self.requestor_map[requestor_id][0] = self.sticky_map_version
                out((self.sticky_map, {}))

    def dequeue(self, headers, out):
        # Sticky Map doesn't support AUTH.
        requestor_id = headers["SESS"]
        if requestor_id not in self.requestor_map:
            self.requestor_map[requestor_id] = [0, out]

        if self.sticky_map_version != self.requestor_map[requestor_id][0]:
            self.requestor_map[requestor_id][0] = self.sticky_map_version
            out((self.sticky_map, {}))


class MessageHandler(StreamRequestHandler):
    def handle(self):
        response_queue = Queue()
        thread = Thread(target=self.process_queue, args=(response_queue,))
        thread.start()
        fileno = self.request.fileno()
        self.server.add_connection(self.request, self.rfile, self.wfile)

        try:
            while True:
                session_id = "NO-SESSION-ID"
                try:
                    msg = read_message(self.rfile)
                    session_id = msg.headers.get("SESS", session_id)
                    self.server.handle_message(msg, response_queue)
                except WeaveException as e:
                    response = exception_to_message(e)
                    response.headers["SESS"] = session_id
                    response_queue.put(response)
                    continue
                except (IOError, ValueError):
                    break
        finally:
            response_queue.put(None)
            thread.join()
            self.server.remove_connection(fileno)


    def process_queue(self, response_queue):
        while True:
            msg = response_queue.get()
            if msg is None:
                break

            try:
                self.reply(serialize_message(msg))
            except IOError:
                break
            finally:
                response_queue.task_done()

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
        self.apps_auth = apps_auth
        self.active_connections = {}
        self.active_connections_lock = RLock()

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

    def handle_message(self, msg, out_queue):
        session_id = get_required_field(msg.headers, "SESS")
        self.preprocess(msg)

        def handle_dequeue(obj):
            task, headers = obj
            msg = Message("inform", task)
            msg.headers.update(headers)
            msg.headers["SESS"] = session_id
            out_queue.put(msg)

        if msg.operation == "dequeue":
            self.handle_dequeue(msg, handle_dequeue)
        elif msg.operation == "enqueue":
            self.handle_enqueue(msg)
            msg = Message("result")
            msg.headers["RES"] = "OK"
            msg.headers["SESS"] = session_id
            out_queue.put(msg)
        elif msg.operation == "create":
            queue_name = self.handle_create(msg)
            msg = Message("result")
            msg.headers["RES"] = "OK"
            msg.headers["Q"] = queue_name
            msg.headers["SESS"] = session_id
            out_queue.put(msg)
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

    def handle_dequeue(self, msg, out_queue):
        queue_name = get_required_field(msg.headers, "Q")
        try:
            queue = self.queue_map[queue_name]
        except KeyError:
            raise ObjectNotFound(queue_name)
        queue.dequeue(msg.headers, out_queue)

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

    def unregister_application(self, token):
        return self.apps_auth.pop(token, None)

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

    def add_connection(self, sock, rfile, wfile):
        with self.active_connections_lock:
            self.active_connections[sock.fileno()] = sock, rfile, wfile

    def remove_connection(self, fileno):
        with self.active_connections_lock:
            self.active_connections.pop(fileno)

    def shutdown(self):
        for _, queue in self.queue_map.items():
            queue.disconnect()

        with self.active_connections_lock:
            for sock, rfile, wfile in self.active_connections.values():
                safe_close(rfile)
                safe_close(wfile)
                safe_close(sock)

        super().shutdown()
        super().server_close()
