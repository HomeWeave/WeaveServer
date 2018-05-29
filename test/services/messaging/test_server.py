import random
import socket
from copy import deepcopy
from threading import Thread, Event, Semaphore

import pytest
from weavelib.exceptions import ObjectNotFound, ObjectAlreadyExists
from weavelib.exceptions import SchemaValidationFailed, ProtocolError
from weavelib.exceptions import BadOperation, InternalError, ObjectClosed
from weavelib.exceptions import AuthenticationFailed
from weavelib.messaging import Sender, Receiver, Creator, read_message
from weavelib.messaging import ensure_ok_message

from weaveserver.services.messaging import MessageService
from weaveserver.core.logger import configure_logging


configure_logging()


CONFIG = {
    "redis_config": {
        "USE_FAKE_REDIS": True
    },
    "apps": {
        "auth1": {
            "appid": "blah",
            "type": "SYSTEM"
        },
        "auth2": {
            "appid": "plugin",
            "package": "com.plugin"
        },
        "auth3": {
            "appid": "blah1",
            "type": "SYSTEM"
        },
        "auth4": {
            "appid": "plugin2",
            "package": "com.plugin2"
        }
    }
}

TEST_QUEUES = [
    {
        "queue_name": "a.b.c",
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
    },
    {
        "queue_name": "x.keyedsticky",
        "queue_type": "keyedsticky",
        "request_schema": {"type": "object"}
    }
]


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


def make_receiver(count, obj, sem, r):
    def on_message(msg, headers):
        obj.append(msg)
        sem.release()
        nonlocal count
        count -= 1
        if not count:
            r.stop()
    return on_message


class TestMessagingService(object):
    @classmethod
    def setup_class(cls):
        event = Event()
        cls.service = MessageService(None, CONFIG)
        cls.service.notify_start = lambda: event.set()
        cls.service_thread = Thread(target=cls.service.on_service_start)
        cls.service_thread.start()
        event.wait()
        creator = Creator()
        creator.start()
        for queue_info in TEST_QUEUES:
            creator.create(queue_info, headers={"AUTH": "auth1"})

    @classmethod
    def teardown_class(cls):
        cls.service.on_service_stop()
        cls.service_thread.join()

    def test_connect_disconnect(self):
        with pytest.raises(IOError):
            send_raw('')

    def test_bad_structure(self):
        with pytest.raises(ProtocolError):
            send_raw("sdkhsds-ss!3l")

    def test_required_fields_missing(self):
        with pytest.raises(ProtocolError):
            send_raw("HDR enqueue\nMSG blah\n\n")

    def test_bad_operation(self):
        with pytest.raises(BadOperation):
            send_raw('MSG {"a": "b"}\nOP bad-operation\nQ a.b.c\n\n')

    def test_bad_json(self):
        with pytest.raises(ProtocolError):
            send_raw('MSG {a": "b"}\nOP enqueue\nQ a.b.c\n\n')

    def test_enqueue_without_queue_header(self):
        with pytest.raises(ProtocolError):
            send_raw('MSG {"a": "b"}\nOP enqueue\n\n')

    def test_enqueue_without_task(self):
        s = Sender("/a.b.c")
        s.start()
        with pytest.raises(ProtocolError):
            s.send(None)

    def test_enqueue_to_unknown_queue(self):
        s = Sender("unknown.queue")
        s.start()
        with pytest.raises(ObjectNotFound):
            s.send({"a": "b"})

    def test_dequeue_from_unknown_queue(self):
        r = Receiver("unknown.queue")
        r.start()
        with pytest.raises(ObjectNotFound):
            r.receive()

    def test_dequeue_without_required_header(self):
        with pytest.raises(ProtocolError):
            send_raw('OP dequeue\n\n')

    def test_enqueue_with_bad_schema(self):
        s = Sender("/a.b.c")
        s.start()
        with pytest.raises(SchemaValidationFailed):
            s.send({"foo": [1, 2]})

    def test_simple_enqueue_dequeue(self):
        msgs = []

        s = Sender("/a.b.c")
        r = Receiver("/a.b.c")
        s.start()
        r.start()
        r.on_message = lambda msg, hdrs: msgs.append(msg) or r.stop()

        s.send({"foo": "bar"})
        thread = Thread(target=r.run)
        thread.start()

        thread.join()

        assert msgs == [{"foo": "bar"}]

    def test_multiple_enqueue_dequeue(self):
        obj = {"foo": "bar"}

        s = Sender("/a.b.c")
        r = Receiver("/a.b.c")

        s.start()
        for _ in range(10):
            s.send(obj)

        expected_message_count = 10

        def on_message(msg, headers):
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

    def test_multiple_client_disconnection(self):
        # Two clients waiting on a queue. First one disconnects. Second should
        # get it.
        sem1 = Semaphore(0)
        sem2 = Semaphore(0)
        msgs1 = []
        msgs2 = []
        op = {"foo": "bar"}

        s = Sender("/a.b.c")
        s.start()

        r1 = Receiver("/a.b.c")
        r1.on_message = make_receiver(1, msgs1, sem1, r1)
        r1.start()
        t1 = Thread(name="Receiver1", target=r1.run)
        t1.start()

        r2 = Receiver("/a.b.c")
        r2.on_message = make_receiver(1, msgs2, sem2, r2)
        r2.start()
        t2 = Thread(name="Receiver2", target=r2.run)
        t2.start()

        # Stop the Receiver1, the data should be recvd by r2 even if r1 was
        # first to request.
        r1.stop()
        t1.join()

        s.send(op)

        assert sem2.acquire(timeout=5)
        assert msgs2[0] == op

    def test_sticky_simple_enqueue_dequeue(self):
        sem1 = Semaphore(0)
        sem2 = Semaphore(0)
        msgs1 = []
        msgs2 = []
        op = {"foo": "bar"}

        s = Sender("/a.sticky")
        s.start()
        r1 = Receiver("/a.sticky")
        r1.on_message = make_receiver(2, msgs1, sem1, r1)
        r1.start()
        Thread(target=r1.run).start()

        assert not sem1.acquire(timeout=2)  # Assert that this times out.
        assert len(msgs1) == 0

        s.send(op)
        assert sem1.acquire(timeout=10)  # This shouldn't timeout.
        assert len(msgs1) == 1

        assert not sem1.acquire(timeout=2)  # This should timeout again.
        assert len(msgs1) == 1

        r2 = Receiver("/a.sticky")
        r2.on_message = make_receiver(2, msgs2, sem2, r2)
        r2.start()
        Thread(target=r2.run).start()

        assert sem2.acquire(timeout=10)  # This shouldn't timeout.
        assert len(msgs2) == 1

        assert not sem2.acquire(timeout=2)  # This should timeout.

        s.send(op)
        assert sem1.acquire(timeout=10)
        assert sem2.acquire(timeout=2)

        assert len(msgs1) == 2
        assert len(msgs2) == 2

    def test_keyed_enqueue_without_key_header(self):
        s = Sender("/x.keyedsticky")
        s.start()
        with pytest.raises(ProtocolError):
            s.send({"foo": "bar"})

    def test_keyed_sticky(self):
        s1 = Sender("/x.keyedsticky")
        s2 = Sender("/x.keyedsticky")
        obj1 = []
        obj2 = []
        sem1 = Semaphore(0)
        sem2 = Semaphore(0)
        r1 = Receiver("/x.keyedsticky")
        r2 = Receiver("/x.keyedsticky")

        r1.on_message = make_receiver(4, obj1, sem1, r1)
        r1.start()
        Thread(target=r1.run).start()

        assert sem1.acquire(timeout=10)  # Won't timeout for the first message.
        assert obj1[-1] == {}

        s1.start()
        s1.send({"foo": "bar"}, headers={"KEY": "1"})
        assert sem1.acquire(timeout=10)  # Must not timeout.
        assert obj1[-1] == {"1": {"foo": "bar"}}

        r2.on_message = make_receiver(3, obj2, sem2, r2)
        r2.start()
        Thread(target=r2.run).start()

        assert sem2.acquire(timeout=10)  # Must not timeout.
        assert obj2[-1] == {"1": {"foo": "bar"}}

        s2.start()
        s2.send({"baz": "grr"}, headers={"KEY": "2"})
        assert sem1.acquire(timeout=10)
        assert sem2.acquire(timeout=10)
        assert obj1[-1] == {"1": {"foo": "bar"}, "2": {"baz": "grr"}}
        assert obj2[-1] == {"1": {"foo": "bar"}, "2": {"baz": "grr"}}

        s2.send({"foo": "hello"}, headers={"KEY": "1"})
        assert sem1.acquire(timeout=10)
        assert sem2.acquire(timeout=10)
        assert obj1[-1] == {"1": {"foo": "hello"}, "2": {"baz": "grr"}}
        assert obj2[-1] == {"1": {"foo": "hello"}, "2": {"baz": "grr"}}

    def test_create_queue_with_no_payload(self):
        with pytest.raises(ProtocolError):
            send_raw("OP create\n\n")

    def test_create_duplicate_queues(self):
        queue_info = {
            "queue_name": "dummy",
            "request_schema": {"type": "object"}
        }
        creator = Creator()
        creator.start()
        creator.create(queue_info, headers={"AUTH": "auth1"})

        with pytest.raises(ObjectAlreadyExists):
            creator.create(queue_info, headers={"AUTH": "auth1"})

    def test_create_bad_schema_object(self):
        queue_info = {
            "queue_name": "bad-schema",
            "request_schema": [1, 2, 3]
        }
        creator = Creator()
        creator.start()
        with pytest.raises(SchemaValidationFailed):
            creator.create(queue_info, headers={"AUTH": "auth1"})

    def test_create_incorrect_schema(self):
        queue_info = {
            "queue_name": "bad-schema",
            "request_schema": {"type": "wrong"}
        }
        creator = Creator()
        creator.start()
        with pytest.raises(SchemaValidationFailed):
            creator.create(queue_info, headers={"AUTH": "auth1"})

    def test_create_without_request_schema(self):
        queue_info = {
            "queue_name": "bad-schema",
        }
        creator = Creator()
        creator.start()
        with pytest.raises(SchemaValidationFailed):
            creator.create(queue_info, headers={"AUTH": "auth1"})

    def test_system_app_queue_create(self):
        queue = "/system/app/queue/create"
        queue_info = {"queue_name": queue, "request_schema": {"type": "string"}}
        creator = Creator()
        creator.start()
        assert creator.create(queue_info, headers={"AUTH": "auth1"}) == queue

    def test_plugin_queue_create(self):
        queue = "/app/queue/create"
        queue_info = {"queue_name": queue, "request_schema": {"type": "string"}}
        creator = Creator()
        creator.start()

        res = "/plugins/com.plugin/plugin/app/queue/create"
        assert creator.create(queue_info, headers={"AUTH": "auth2"}) == res

    def test_enqueue_sessionized_without_key(self):
        queue_info = {
            "queue_name": "/test.sessionized",
            "queue_type": "sessionized",
            "request_schema": {"type": "string"}
        }
        creator = Creator()
        creator.start()
        creator.create(queue_info, headers={"AUTH": "auth1"})

        sender = Sender("/test.sessionized")
        sender.start()
        with pytest.raises(ProtocolError):
            sender.send("test")

        receiver = Receiver("/test.sessionized")
        receiver.start()

        with pytest.raises(ProtocolError):
            receiver.receive()

    def test_simple_sessionized_enqueue_dequeue(self):
        queue_info = {
            "queue_name": "/test.sessionized2",
            "queue_type": "sessionized",
            "request_schema": {"type": "string"}
        }
        creator = Creator()
        creator.start()
        creator.create(queue_info, headers={"AUTH": "auth1"})

        sender1 = Sender("/test.sessionized2")
        sender1.start()
        sender1.send("test", headers={"COOKIE": "xyz"})

        sender2 = Sender("/test.sessionized2")
        sender2.start()
        sender2.send("diff", headers={"COOKIE": "diff"})

        receiver1 = Receiver("/test.sessionized2", cookie="xyz")
        receiver1.start()

        receiver2 = Receiver("/test.sessionized2", cookie="diff")
        receiver2.start()

        assert receiver1.receive().task == "test"
        assert receiver2.receive().task == "diff"

        # Test retrieving items for the second time.
        event = Event()
        receiver2.on_message = lambda x, y: event.set()
        thread = Thread(target=receiver2.run)
        thread.start()

        sender1.send("test2", headers={"COOKIE": "xyz"})
        assert receiver1.receive().task == "test2"

        receiver2.stop()
        thread.join()

    def test_several_sessionized_queues(self):
        queue_info = {
            "queue_name": "/test.sessionized/several",
            "queue_type": "sessionized",
            "request_schema": {"type": "string"}
        }
        creator = Creator()
        creator.start()
        creator.create(queue_info, headers={"AUTH": "auth1"})

        senders = []
        receivers = []
        cookies = []
        texts = []

        for i in range(10):
            cookie = "c-" + str(i)
            cookies.append(cookie)

            sender = Sender("/test.sessionized/several")
            sender.start()
            senders.append(sender)

            receiver = Receiver("/test.sessionized/several", cookie=cookie)
            receiver.start()
            receivers.append(receiver)

            text = "text" + str(i)
            texts.append(text)

        arr = list(range(10))[::-1]
        random.shuffle(arr)

        # Send requests in random order
        for pos in arr:
            senders[pos].send(texts[pos], headers={"COOKIE": cookies[pos]})

        for i in range(10):
            assert texts[i] == receivers[i].receive().task

    def test_fifo_enqueue_dequeue(self):
        queue_info = {
            "queue_name": "/test.fifo/simple",
            "queue_type": "fifo",
            "request_schema": {"type": "string"}
        }
        creator = Creator()
        creator.start()
        creator.create(queue_info, headers={"AUTH": "auth1"})

        msgs1 = []
        sem1 = Semaphore(0)
        receiver1 = Receiver("/test.fifo/simple")
        receiver1.on_message = make_receiver(2, msgs1, sem1, receiver1)
        receiver1.start()
        Thread(target=receiver1.run).start()

        msgs2 = []
        sem2 = Semaphore(0)
        receiver2 = Receiver("/test.fifo/simple")
        receiver2.on_message = make_receiver(2, msgs2, sem2, receiver2)
        receiver2.start()
        Thread(target=receiver2.run).start()

        sender1 = Sender("/test.fifo/simple")
        sender1.start()

        sender1.send("test")

        assert sem1.acquire(timeout=10)
        assert msgs1[-1] == "test"
        assert not sem2.acquire(timeout=2)

        sender1.send("test2")

        assert sem2.acquire(timeout=10)
        assert msgs2[-1] == "test2"
        assert not sem1.acquire(timeout=2)

        sender1.send("test3")

        assert sem1.acquire(timeout=10)
        assert msgs1[-1] == "test3"
        assert not sem2.acquire(timeout=2)

        sender1.send("test4")

        assert sem2.acquire(timeout=10)
        assert msgs2[-1] == "test4"
        assert not sem1.acquire(timeout=2)


    def test_no_auth_create(self):
        queue_info = {
            "queue_name": "/test.auth/1",
            "request_schema": {"type": "string"}
        }
        creator = Creator()
        creator.start()
        with pytest.raises(ProtocolError):
            creator.create(queue_info)

        with pytest.raises(AuthenticationFailed):
            creator.create(queue_info, headers={"AUTH": "hello"})

    def test_queue_access(self):
        sys_queue = "/system/queue"
        queue_postfix = "/test_plugin"

        sys_creator = Creator(auth="auth1")
        sys_creator.start()

        plugin_creator = Creator(auth="auth2")
        plugin_creator.start()

        plugin_queue = plugin_creator.create({
            "queue_name": queue_postfix,
            "request_schema": {},
            "force_auth": True
        })
        assert sys_queue == sys_creator.create({
            "queue_name": sys_queue,
            "request_schema": {},
            "force_auth": True
        })

        senders = []
        receivers = []

        # auth5 doesn't exist (last iteration).
        for i in range(1, 6):
            senders.append(Sender(sys_queue, auth="auth" + str(i)))
            senders[-1].start()

            senders.append(Sender(plugin_queue, auth="auth" + str(i)))
            senders[-1].start()

            receivers.append(Receiver(sys_queue, auth="auth" + str(i)))
            receivers[-1].start()

            receivers.append(Receiver(plugin_queue, auth="auth" + str(i)))
            receivers[-1].start()

        success_indices = set(range(8))
        fail_indices = {8, 9}

        for idx in success_indices:
            senders[idx].send("test")
            receivers[idx].receive().task == "test"

        for idx in fail_indices:
            with pytest.raises(AuthenticationFailed):
                senders[idx].send("test")

            with pytest.raises(AuthenticationFailed):
                receivers[idx].receive()

    def test_queue_authorization(self):
        pass


class TestMessageServiceClosure(object):
    @pytest.mark.parametrize("queue_type,cookie",
                             [("fifo", (x for x in ("a", "b"))),
                              ("sticky", (x for x in ("a", "b"))),
                              ("keyedsticky", (x for x in ("a", "b"))),
                              ("sessionized", (x for x in ("a", "b")))])
    def test_queue_closure(self, queue_type, cookie):
        event = Event()
        service = MessageService(None, CONFIG)
        service.notify_start = event.set
        thread = Thread(target=service.on_service_start)
        thread.start()
        event.wait()

        creator = Creator(auth="auth1")
        creator.start()
        creator.create({
            "queue_name": "/fifo-closure",
            "request_schema": {},
            "queue_type": queue_type
        })

        def patch_receive(receiver, event):
            original = receiver.receive
            def receive():
                event.set()
                original()
            receiver.receive = receive

        def wrap_run(receiver):
            def run():
                try:
                    receiver.run()
                except QueueClosed:
                    pass
            return run

        e1 = Event()
        r1 = Receiver("/fifo-closure", cookie=next(cookie))
        r1.start()
        patch_receive(r1, e1)
        t1 = Thread(target=wrap_run(r1))
        t1.start()

        e2 = Event()
        r2 = Receiver("/fifo-closure", cookie=next(cookie))
        r2.start()
        patch_receive(r2, e2)
        t2 = Thread(target=wrap_run(r2))
        t2.start()

        e1.wait()
        e2.wait()

        service.on_service_stop()
        thread.join()
        t1.join()
        t2.join()
