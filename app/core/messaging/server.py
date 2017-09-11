import json
import logging
import re
from socketserver import ThreadingTCPServer, StreamRequestHandler

from retask import Queue, Task
from jsonschema import validate, ValidationError

logger = logging.getLogger(__name__)


class MessagingException(Exception):
    pass


class InvalidMessageStructure(MessagingException):
    pass


class WaitTimeoutError(MessagingException):
    pass


class QueueNotFound(MessagingException):
    pass


class Message(object):
    def __init__(self, op, queue, msg=None):
        self.op = op
        self.queue = queue
        self.json = msg

    @property
    def target(self):
        return self.queue

    @property
    def operation(self):
        return self.op

    @property
    def task(self):
        return self.json

    @task.setter
    def set_task(self, val):
        self.json = val


class MessageQueue(Queue):
    def __init__(self, queue_info, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue_info = queue_info

    def enqueue(self, task):
        logger.info("validation of: %s", task.data)
        validate(task.data, self.queue_info["request_schema"])
        super().enqueue(task)
        return True


class QueueProcessor(object):
    def __init__(self, redis_config, queues, server):
        self.redis_config = redis_config
        self.queue_map = {x["queue_name"]: self.create_queue(x) for x in queues}
        self.server = server

    def create_queue(self, queue_info):
        queue_name = queue_info["queue_name"]
        return MessageQueue(queue_info, queue_name, self.redis_config)

    def start(self):
        for queue in self.queue_map.values():
            queue.connect()
            logger.info("Connected: %s", queue)

    def enqueue(self, queue_name, task):
        try:
            queue = self.queue_map.get(queue_name)
        except KeyError:
            raise QueueNotFound
        queue.enqueue(task)
        return True

    def dequeue(self, queue_name):
        try:
            queue = self.queue_map.get(queue_name)
        except KeyError:
            raise QueueNotFound
        return queue.wait()

    def wait(self):
        for _, queue_info in self.queue_map.items():
            queue_info["thread"].join()


class MessageHandler(StreamRequestHandler):
    def handle(self):
        logger.info("Client connected.")
        while True:
            # Reading group of lines
            lines = []
            line_read = False
            while True:
                line = self.rfile.readline().strip()
                if line:
                    lines.append(line.decode("UTF-8"))
                    line_read = True
                else:
                    break

                if not line_read:
                    break
            for resp in self.handle_lines(lines):
                self.wfile.write((resp + "\n").encode())

        logger.info("Client disconnected.")

    def handle_lines(self, lines):
        try:
            msg = self.parse_message(lines)
        except InvalidMessageStructure:
            logging.warning("invalid message: %s", lines)
            yield "INVALID-MESSAGE-STRUCTURE"
            raise StopIteration

        if msg.operation == "dequeue":
            for item in self.handle_dequeue(msg):
                yield item
        elif msg.operation == "enqueue":
            for item in self.handle_enqueue(msg):
                yield item
        else:
            yield "BAD-OPERATION"

    def handle_enqueue(self, msg):
        if msg.task is None:
            yield "INVALID-ENQUEUE-STRUCTURE"
            raise StopIteration

        try:
            if self.server.on_task(msg.target, msg.task):
                yield "OK"
            else:
                yield "FAILED"
        except QueueNotFound:
            yield "QUEUE-NOT-FOUND"
        except Exception:
            logging.exception("Internal error.")
            yield "INTERNAL-ERROR"

    def handle_dequeue(self, msg):
        while True:
            yield self.server.get_task(msg.target())

    @staticmethod
    def parse_message(lines):
        required_fields = {"OP", "Q"}
        fields = {}
        for line in lines:
            line_parts = line.split(" ", 1)
            fields[line_parts[0]] = line_parts[1]

        if required_fields - set(fields.keys()):
            raise InvalidMessageStructure

        if "MSG" in fields:
            obj = json.loads(fields["MSG"])
            task = Task(obj)
        else:
            task = None
        return Message(fields["OP"], fields["Q"], task)


class MessageServer(ThreadingTCPServer):
    allow_reuse_address = True

    def __init__(self, port, redis_config, queues):
        super().__init__(("", port), MessageHandler)
        self.listener_map = {}
        self.queue_processor = QueueProcessor(redis_config, queues, self)

    def on_task(self, queue_name, task):
        self.queue_processor.enqueue(queue_name, task)
        return True

    def get_task(self, queue_name):
        return self.queue_processor.dequeue(queue_name)

    def get_listeners(self, queue_name):
        return self.listener_map.get(queue_name, [])

    def write_listener(self, listener, queue_info, task):
        pass

    def run(self):
        self.queue_processor.start()
        self.serve_forever()
