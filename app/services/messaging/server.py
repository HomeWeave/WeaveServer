import logging
from socketserver import ThreadingTCPServer, StreamRequestHandler
from threading import Condition, RLock
from queue import Queue as SyncQueue
from uuid import uuid4

from retask import Queue
from jsonschema import validate, ValidationError

from app.core.messaging import read_message, serialize_message, Message
from app.core.messaging import SchemaValidationFailed, BadOperation
from app.core.messaging import RequiredFieldsMissing
from app.core.messaging import MessagingException, QueueNotFound
from app.core.service_base import BaseService, BackgroundProcessServiceStart


logger = logging.getLogger(__name__)


class BaseQueue(object):
    def __init__(self, queue_info):
        self.queue_info = queue_info

    def enqueue(self, task):
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
    def __init__(self, queue_info, *args, **kwargs):
        super().__init__(queue_info)
        self.queue = Queue(*args, **kwargs)

    def enqueue(self, task):
        self.validate_schema(task.data)
        self.queue.enqueue(task)
        return True

    def dequeue(self, requestor_id):
        return self.queue.wait()

    def connect(self):
        return self.queue.connect()


class DummyQueue(BaseQueue):
    def __init__(self, queue_info, *args, **kwargs):
        super().__init__(queue_info)
        self.queue = SyncQueue()

    def enqueue(self, task):
        self.validate_schema(task.data)
        self.queue.put(task)
        return True

    def dequeue(self, requestor_id):
        return self.queue.get()


class StickyQueue(object):
    def __init__(self, queue_info, *args, **kwargs):
        super().__init__(queue_info)
        self.sticky_message = None
        self.requestors = set()
        self.requestor_lock = RLock()
        self.condition = Condition(self.requestor_lock)

    def enqueue(self, task):
        self.validate_schema(task.data)
        self.sticky_message = task
        self.condition.notify_all()

    def dequeue(self, requestor_id):
        if requestor_id in self.requestors:
            pass

    def connect(self):
        return True


class MessageHandler(StreamRequestHandler):
    def handle(self):
        while True:
            try:
                msg = read_message(self.rfile)
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

    def __init__(self, service, port, redis_config, queue_config):
        super().__init__(("", port), MessageHandler)
        self.service = service
        self.sent_start_notification = False
        self.queue_map = {}
        self.listener_map = {}
        self.sticky_messages = {}

        queue_types = {
            "redis": RedisQueue,
            "dummy": DummyQueue,
            "sticky": StickyQueue
        }
        for queue_info in queue_config["queues"]:
            queue_name = queue_info["queue_name"]
            cls = queue_types[queue_info.get("queue_type", "redis")]
            queue = cls(queue_info, queue_name, redis_config)
            self.queue_map[queue_name] = queue

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
            raise BadOperation

    def handle_enqueue(self, msg):
        if msg.task is None:
            raise RequiredFieldsMissing
        try:
            queue_name = msg.headers["Q"]
        except KeyError:
            raise RequiredFieldsMissing

        try:
            queue = self.queue_map[queue_name]
            queue.enqueue(msg.task)
        except KeyError:
            raise QueueNotFound
        except ValidationError:
            raise SchemaValidationFailed

    def handle_dequeue(self, msg):
        try:
            queue_name = msg.headers["Q"]
        except KeyError:
            raise RequiredFieldsMissing

        try:
            queue = self.queue_map[queue_name]
        except KeyError:
            raise QueueNotFound
        requestor_id = str(uuid4())
        return queue.dequeue(requestor_id)

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
