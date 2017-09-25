import socket
from threading import Thread, Event

from retask import Task
import pytest

from app.core.messaging import Sender, Receiver, RequiredFieldsMissing
from app.core.messaging import QueueNotFound, SchemaValidationFailed
from app.services.messaging import MessageService


CONFIG = {
    "redis_config": {},
    "queues": {
        "queues": [
            {
                "queue_name": "a.b.c",
                "queue_type": "dummy",
                "request_schema": {
                    "type": "object",
                    "properties": {
                        "foo": {
                            "type": "string"
                        }
                    },
                    "required": ["foo"]
                }
            }
        ]
    }
}


def send_raw(msg):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("localhost", Sender.PORT))
    wfile = sock.makefile('wb', Sender.WRITE_BUF_SIZE)
    rfile = sock.makefile('rb', Sender.READ_BUF_SIZE)

    wfile.write(msg.encode())
    wfile.flush()
    sock.shutdown(socket.SHUT_WR)

    resp = rfile.readline().decode("UTF-8").strip()

    sock.close()

    return resp


class TestMessagingService(object):
    @classmethod
    def setup_class(cls):
        event = Event()
        cls.service = MessageService(CONFIG)
        cls.service.notify_start = lambda: event.set()
        cls.service_thread = Thread(target=cls.service.on_service_start)
        cls.service_thread.start()
        event.wait()
        print("Server started.")

    @classmethod
    def teardown_class(cls):
        cls.service.on_service_stop()
        cls.service_thread.join()

    def test_connect_disconnect(self):
        assert send_raw('') == ''

    def test_bad_structure(self):
        assert send_raw("sdkhsds-ssgdlks!!3l") == "INVALID-MESSAGE-STRUCTURE"

    def test_required_fields_missing(self):
        assert send_raw("OP enqueue\nMSG blah\n\n") == "REQUIRED-FIELDS-MISSING"

    def test_bad_operation(self):
        assert send_raw('MSG {"a": "b"}\n'
                        'OP bad-operation\n'
                        'Q a.b.c\n\n') == "BAD-OPERATION"

    def test_bad_json(self):
        assert send_raw('MSG {a": "b"}\n'
                        'OP enqueue\n'
                        'Q a.b.c\n\n') == "SCHEMA-VALIDATION-FAILED"

    def test_enqueue_without_task(self):
        s = Sender("a.b.c")
        s.start()
        with pytest.raises(RequiredFieldsMissing):
            s.send(None)

    def test_enqueue_to_unknown_queue(self):
        s = Sender("unknown.queue")
        s.start()
        with pytest.raises(QueueNotFound):
            s.send(Task({"a": "b"}))

    def test_enqueue_with_bad_schema(self):
        s = Sender("a.b.c")
        s.start()
        with pytest.raises(SchemaValidationFailed):
            s.send(Task({"foo": [1, 2]}))

    def test_simple_enqueue_dequeue(self):
        msgs = []

        s = Sender("a.b.c")
        s.start()
        s.send(Task({"foo": "bar"}))

        r = Receiver("a.b.c")
        r.start()
        r.on_message = lambda msg: msgs.append(msg) or r.stop()
        thread = Thread(target=r.run)
        thread.start()

        thread.join()

        assert msgs == [{"foo": "bar"}]

    def test_multiple_enqueue_dequeue(self):
        obj = {"foo": "bar"}

        s = Sender("a.b.c")
        r = Receiver("a.b.c")

        s.start()
        for _ in range(10):
            s.send(Task(obj))

        expected_message_count = 10

        def on_message(msg):
            assert msg == obj
            nonlocal expected_message_count
            if expected_message_count == 1:
                r.stop()
            expected_message_count -= 1
        r.start()
        r.on_message = on_message
        thread = Thread(target=r.run)
        thread.start()

        thread.join()