import json
import logging
import os
try:
    from queue import Queue
except ImportError:
    from Queue import Queue
import socket
import time
from collections import defaultdict
from socketserver import ThreadingTCPServer, StreamRequestHandler
from threading import RLock, Thread

from jsonschema import validate, ValidationError, SchemaError

from weavelib.exceptions import WeaveException, ObjectNotFound
from weavelib.exceptions import ObjectAlreadyExists, AuthenticationFailed
from weavelib.exceptions import ProtocolError, BadOperation, InternalError
from weavelib.exceptions import SchemaValidationFailed
from weavelib.messaging import read_message, serialize_message, Message
from weavelib.messaging import exception_to_message

from .messaging_utils import get_required_field


logger = logging.getLogger(__name__)


def safe_close(obj):
    try:
        obj.close()
    except (IOError, OSError):
        pass


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
                sock.shutdown(socket.SHUT_RDWR)
                safe_close(sock)
                safe_close(rfile)
                safe_close(wfile)

        super().shutdown()
        super().server_close()
