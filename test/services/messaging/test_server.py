import socket
from threading import Thread, Event, Semaphore

from retask import Task
import pytest

from app.core.messaging import Sender, Receiver, RequiredFieldsMissing
from app.core.messaging import QueueNotFound, SchemaValidationFailed
from app.core.messaging import InvalidMessageStructure, BadOperation
from app.core.messaging import read_message, ensure_ok_message
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
            },
            {
                "queue_name": "a.sticky",
                "queue_type": "sticky",
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

    msg = read_message(rfile)

    sock.close()

    ensure_ok_message(msg)


class TestMessagingService(object):
    @classmethod
    def setup_class(cls):
        event = Event()
        cls.service = MessageService(CONFIG)
        cls.service.notify_start = lambda: event.set()
        cls.service_thread = Thread(target=cls.service.on_service_start)
        cls.service_thread.start()
        event.wait()

    @classmethod
    def teardown_class(cls):
        cls.service.on_service_stop()
        cls.service_thread.join()

    def test_connect_disconnect(self):
        with pytest.raises(IOError):
            send_raw('')

    def test_bad_structure(self):
        with pytest.raises(InvalidMessageStructure):
            send_raw("sdkhsds-ss!3l")

    def test_required_fields_missing(self):
        with pytest.raises(RequiredFieldsMissing):
            send_raw("HDR enqueue\nMSG blah\n\n")

    def test_bad_operation(self):
        with pytest.raises(BadOperation):
            send_raw('MSG {"a": "b"}\nOP bad-operation\nQ a.b.c\n\n')

    def test_bad_json(self):
        with pytest.raises(SchemaValidationFailed):
            send_raw('MSG {a": "b"}\nOP enqueue\nQ a.b.c\n\n')

    def test_enqueue_without_queue_header(self):
        with pytest.raises(RequiredFieldsMissing):
            send_raw('MSG {"a": "b"}\nOP enqueue\n\n')

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

    def test_dequeue_from_unknown_queue(self):
        r = Receiver("unknown.queue")
        r.start()
        with pytest.raises(QueueNotFound):
            r.receive()

    def test_enqueue_with_bad_schema(self):
        s = Sender("a.b.c")
        s.start()
        with pytest.raises(SchemaValidationFailed):
            s.send(Task({"foo": [1, 2]}))

    def test_simple_enqueue_dequeue(self):
        msgs = []

        s = Sender("a.b.c")
        r = Receiver("a.b.c")
        s.start()
        r.start()
        r.on_message = lambda msg: msgs.append(msg) or r.stop()

        s.send(Task({"foo": "bar"}))
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

    def test_stick_simple_enqueue_dequeue(self):
        def make_receiver(count, msgs, sem, r):
            def on_message(msg):
                msgs.append(msg)
                sem.release()
                nonlocal count
                count -= 1
                if not count:
                    r.stop()
            return on_message

        sem1 = Semaphore(0)
        sem2 = Semaphore(0)
        msgs1 = []
        msgs2 = []
        op = {"foo": "bar"}

        s = Sender("a.sticky")
        s.start()
        r1 = Receiver("a.sticky")
        r1.on_message = make_receiver(2, msgs1, sem1, r1)
        r1.start()
        Thread(target=r1.run).start()

        assert not sem1.acquire(timeout=2)  # Assert that this times out.
        assert len(msgs1) == 0

        s.send(Task(op))
        assert sem1.acquire(timeout=10)  # This shouldn't timeout.
        assert len(msgs1) == 1

        assert not sem1.acquire(timeout=2)  # This should timeout again.
        assert len(msgs1) == 1

        r2 = Receiver("a.sticky")
        r2.on_message = make_receiver(2, msgs2, sem2, r2)
        r2.start()
        Thread(target=r2.run).start()

        assert sem2.acquire(timeout=10)  # This shouldn't timeout.
        assert len(msgs2) == 1

        assert not sem2.acquire(timeout=2)  # This should timeout.

        s.send(Task(op))
        assert sem1.acquire(timeout=10)
        assert sem2.acquire(timeout=2)

        assert len(msgs1) == 2
        assert len(msgs2) == 2
