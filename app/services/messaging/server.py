import logging
from socketserver import ThreadingTCPServer, StreamRequestHandler

from retask import Queue
from jsonschema import validate, ValidationError

from app.core.messaging import read_message, serialize_message, QueueNotFound
from app.core.messaging import Message
from app.core.messaging import InvalidMessageStructure
from app.core.service_base import BaseService, BackgroundProcessServiceStart


logger = logging.getLogger(__name__)


class MessageQueue(Queue):
    def __init__(self, queue_info, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue_info = queue_info

    def enqueue(self, task):
        validate(task.data, self.queue_info["request_schema"])
        super().enqueue(task)
        return True


class QueueProcessor(object):
    def __init__(self, redis_config, queue_config, server):
        self.redis_config = {"password": redis_config["REDIS_PASSWD"]}
        queues = queue_config["queues"]
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
            queue = self.queue_map[queue_name]
        except KeyError:
            raise QueueNotFound
        queue.enqueue(task)
        return True

    def dequeue(self, queue_name):
        try:
            queue = self.queue_map.get(queue_name)
        except KeyError:
            raise QueueNotFound
        logger.info("Waiting for queue item...")
        return queue.wait()

    def wait(self):
        for _, queue_info in self.queue_map.items():
            queue_info["thread"].join()


class MessageHandler(StreamRequestHandler):
    def handle(self):
        logger.info("Client connected.")
        while True:
            try:
                msg = read_message(self.rfile)
            except InvalidMessageStructure:
                self.wfile.write("INVALID-MESSAGE-STRUCTURE")
                continue
            for resp in self.handle_message(msg):
                self.wfile.write((resp + "\n").encode())

        logger.info("Client disconnected.")

    def handle_message(self, msg):
        if msg.operation == "dequeue":
            logger.info("Client connected for dequeue.")
            for item in self.handle_dequeue(msg):
                yield serialize_message(Message("inform", msg.target, item))
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
            self.server.on_task(msg.target, msg.task)
            yield "OK"
        except QueueNotFound:
            yield "QUEUE-NOT-FOUND"
        except ValidationError:
            yield "INVALID-SCHEMA"
        except Exception:
            logging.exception("Internal error.")
            yield "INTERNAL-ERROR"

    def handle_dequeue(self, msg):
        while True:
            yield self.server.get_task(msg.target)


class MessageServer(ThreadingTCPServer):
    allow_reuse_address = True

    def __init__(self, service, port, redis_config, queue_config):
        super().__init__(("", port), MessageHandler)
        self.listener_map = {}
        self.queue_processor = QueueProcessor(redis_config, queue_config, self)
        self.service = service
        self.sent_start_notification = False

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
        logger.info("Starting message server..")
        self.serve_forever()

    def service_actions(self):
        if not self.sent_start_notification:
            self.service.notify_start()
            self.sent_start_notification = True


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
