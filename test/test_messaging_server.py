import random
import socket
from copy import deepcopy
from threading import Thread, Event, Semaphore

import pytest
from weavelib.exceptions import ObjectNotFound, ObjectAlreadyExists
from weavelib.exceptions import SchemaValidationFailed, ProtocolError
from weavelib.exceptions import BadOperation, InternalError, ObjectClosed
from weavelib.exceptions import AuthenticationFailed
from weavelib.messaging import Sender, Receiver, read_message
from weavelib.messaging import ensure_ok_message, WeaveConnection

from messaging.server import MessageServer
from messaging.application_registry import ApplicationRegistry, Plugin
from messaging.queue_manager import ChannelRegistry
from messaging.synonyms import SynonymRegistry


import logging


logging.basicConfig()


def send_raw(msg):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("localhost", WeaveConnection.PORT))
    wfile = sock.makefile('wb', WeaveConnection.WRITE_BUF_SIZE)
    rfile = sock.makefile('rb', WeaveConnection.READ_BUF_SIZE)

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


class TestMessageServer(object):
    @classmethod
    def setup_class(cls):
        event = Event()

        schema = {
            "type": "object",
            "properties": {
                "foo": {
                    "type": "string"
                }
            },
            "required": ["foo"]
        }

        test_app = Plugin("test", "test", "test-token")
        apps = ApplicationRegistry()
        registry = ChannelRegistry(apps)
        registry.create_queue("/a.b.c", test_app, schema, {}, 'fifo')
        registry.create_queue("/test.sessionized", test_app, {"type": "string"},
                              {}, 'sessionized')
        registry.create_queue("/test.sessionized2", test_app,
                              {"type": "string"}, {}, 'sessionized')
        registry.create_queue("/test.sessionized/several", test_app,
                              {"type": "string"}, {}, 'sessionized')
        registry.create_queue("/test.fifo/simple", test_app, {"type": "string"},
                              {}, 'fifo')
        registry.create_queue("/test.fifo/test-disconnect", test_app,
                              {"type": "string"}, {}, 'fifo')
        registry.create_queue("/test.sessionized/test-disconnect", test_app,
                              {"type": "string"}, {}, 'sessionized')
        registry.create_queue('/multicast/1', test_app, {"type": "string"}, {},
                              'multicast')
        registry.create_queue('/multicast/2', test_app, {"type": "string"}, {},
                              'multicast')

        synonym_registry = SynonymRegistry()
        synonym_registry.register("/multi", "/multicast/2")

        cls.server = MessageServer(11023, apps, registry, synonym_registry,
                                   event.set)
        cls.server_thread = Thread(target=cls.server.run)
        cls.server_thread.start()
        event.wait()
        cls.conn = WeaveConnection.local()
        cls.conn.connect()

    @classmethod
    def teardown_class(cls):
        cls.conn.close()
        cls.server.shutdown()
        cls.server_thread.join()

    def test_connect_disconnect(self):
        with pytest.raises(IOError):
            send_raw('')

    def test_bad_structure(self):
        with pytest.raises(ProtocolError):
            send_raw("sdkhsds\n-ss!3l")

    def test_required_fields_missing(self):
        with pytest.raises(ProtocolError):
            send_raw("HDR push\nMSG blah\n\n")

    def test_bad_operation(self):
        with pytest.raises(BadOperation):
            send_raw('MSG {"a": "b"}\nSESS 1\nOP bad-operation\nC /a.b.c\n\n')

    def test_bad_json(self):
        with pytest.raises(ProtocolError):
            send_raw('MSG {a": "b"}\nOP push\nQ a.b.c\n\n')

    def test_push_without_queue_header(self):
        with pytest.raises(ProtocolError):
            send_raw('MSG {"a": "b"}\nOP push\n\n')

    def test_push_without_task(self):
        s = Sender(self.conn, "/a.b.c")
        s.start()
        with pytest.raises(ProtocolError):
            s.send(None)

    def test_push_to_unknown_queue(self):
        s = Sender(self.conn, "unknown.queue")
        s.start()
        with pytest.raises(ObjectNotFound):
            s.send({"a": "b"})

    def test_pop_from_unknown_queue(self):
        r = Receiver(self.conn, "unknown.queue")
        r.start()
        with pytest.raises(ObjectNotFound):
            r.receive()

    def test_pop_without_required_header(self):
        with pytest.raises(ProtocolError):
            send_raw('OP pop\n\n')

    def test_push_with_bad_schema(self):
        s = Sender(self.conn, "/a.b.c")
        s.start()
        with pytest.raises(SchemaValidationFailed):
            s.send({"foo": [1, 2]})

    def test_simple_push_pop(self):
        msgs = []

        s = Sender(self.conn, "/a.b.c")
        r = Receiver(self.conn, "/a.b.c")
        s.start()
        r.start()
        r.on_message = lambda msg, hdrs: msgs.append(msg) or r.stop()

        s.send({"foo": "bar"})
        thread = Thread(target=r.run)
        thread.start()

        thread.join()

        assert msgs == [{"foo": "bar"}]

    def test_multiple_push_pop(self):
        obj = {"foo": "bar"}

        s = Sender(self.conn, "/a.b.c")
        r = Receiver(self.conn, "/a.b.c")

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

    def test_push_sessionized_without_key(self):
        sender = Sender(self.conn, "/test.sessionized")
        sender.start()
        with pytest.raises(ProtocolError):
            sender.send("test")

        receiver = Receiver(self.conn, "/test.sessionized")
        receiver.start()

        with pytest.raises(ProtocolError):
            receiver.receive()

    def test_simple_sessionized_push_pop(self):
        sender1 = Sender(self.conn, "/test.sessionized2")
        sender1.start()
        sender1.send("test", headers={"COOKIE": "xyz"})

        sender2 = Sender(self.conn, "/test.sessionized2")
        sender2.start()
        sender2.send("diff", headers={"COOKIE": "diff"})

        msgs1 = []
        sem1 = Semaphore(0)
        receiver1 = Receiver(self.conn, "/test.sessionized2", cookie="xyz")
        receiver1.on_message = make_receiver(2, msgs1, sem1, receiver1)
        receiver1.start()
        Thread(target=receiver1.run).start()

        msgs2 = []
        sem2 = Semaphore(0)
        receiver2 = Receiver(self.conn, "/test.sessionized2", cookie="diff")
        receiver2.on_message = make_receiver(2, msgs2, sem2, receiver2)
        receiver2.start()
        Thread(target=receiver2.run).start()

        assert sem1.acquire(timeout=10)
        assert sem2.acquire(timeout=10)
        assert msgs1[0] == "test"
        assert msgs2[0] == "diff"

        # Test retrieving items for the second time.
        sender1.send("test2", headers={"COOKIE": "xyz"})
        assert sem1.acquire(timeout=10)
        assert msgs1[1] == "test2"

        assert not sem2.acquire(timeout=5)

    def test_several_sessionized_queues(self):
        senders = []
        receivers = []
        cookies = []
        texts = []

        for i in range(10):
            cookie = "c-" + str(i)
            cookies.append(cookie)

            sender = Sender(self.conn, "/test.sessionized/several")
            sender.start()
            senders.append(sender)

            receiver = Receiver(self.conn, "/test.sessionized/several",
                                cookie=cookie)
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

    def test_fifo_push_pop(self):
        msgs1 = []
        sem1 = Semaphore(0)
        receiver1 = Receiver(self.conn, "/test.fifo/simple")
        receiver1.on_message = make_receiver(2, msgs1, sem1, receiver1)
        receiver1.start()
        Thread(target=receiver1.run).start()

        msgs2 = []
        sem2 = Semaphore(0)
        receiver2 = Receiver(self.conn, "/test.fifo/simple")
        receiver2.on_message = make_receiver(2, msgs2, sem2, receiver2)
        receiver2.start()
        Thread(target=receiver2.run).start()

        sender1 = Sender(self.conn, "/test.fifo/simple")
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

    def test_multicast(self):
        msgs = [[] for _ in range(5)]
        sems = [Semaphore(0) for _ in range(5)]
        receivers = [Receiver(self.conn, '/multicast/1') for _ in range(5)]
        for receiver, sem, msg in zip(receivers, sems, msgs):
            receiver.on_message = make_receiver(1, msg, sem, receiver)
            receiver.start()
            Thread(target=receiver.run).start()

        sender = Sender(self.conn, '/multicast/1')
        sender.start()
        sender.send("test")

        for msg, sem in zip(msgs, sems):
            assert sem.acquire(timeout=10)
            assert msg[-1] == "test"
            assert not sem.acquire(timeout=2)

        sender.close()
        for receiver in receivers:
            receiver.stop()

    def test_multicast_with_synonym(self):
        msgs = []
        sem = Semaphore(0)
        receiver = Receiver(self.conn, "/synonyms/multi")
        receiver.on_message = make_receiver(1, msgs, sem, receiver)
        receiver.start()
        Thread(target=receiver.run).start()

        sender = Sender(self.conn, "/synonyms/multi")
        sender.start()
        sender.send("test")

        assert sem.acquire(timeout=10)
        assert msgs[-1] == "test"
        assert not sem.acquire(timeout=2)

    @pytest.mark.parametrize("queue_name",
                             ["/test.fifo/test-disconnect",
                              "/test.sessionized/test-disconnect"])
    def test_queue_waits_removed_after_client_disconnects(self, queue_name):
        conn1 = WeaveConnection.local()
        conn2 = WeaveConnection.local()
        conn3 = WeaveConnection.local()
        conn1.connect()
        conn2.connect()
        conn3.connect()

        msgs1 = []
        sem1 = Semaphore(0)
        receiver1 = Receiver(conn1,queue_name, cookie="a")
        receiver1.on_message = make_receiver(1, msgs1, sem1, receiver1)
        receiver1.start()
        Thread(target=receiver1.run).start()

        msgs2 = []
        sem2 = Semaphore(0)
        receiver2 = Receiver(conn2, queue_name, cookie="b")
        receiver2.on_message = make_receiver(1, msgs2, sem2, receiver2)
        receiver2.start()
        Thread(target=receiver2.run).start()

        conn1.close()

        import time; time.sleep(1)

        sender1 = Sender(conn3, queue_name)
        sender1.start()

        sender1.send("test", headers={"COOKIE": "b"})

        assert sem2.acquire(timeout=5)
        assert msgs2[-1] == "test"

        conn2.close()
        conn3.close()


class TestMessageServerClosure(object):

    @pytest.mark.parametrize("queue_type,cookie",
                             [("fifo", (x for x in ("a", "b"))),
                              ("sessionized", (x for x in ("a", "b")))])
    def test_queue_closure(self, queue_type, cookie):
        event = Event()
        test_app = Plugin("test", "test", "test-token")
        apps = ApplicationRegistry()
        registry = ChannelRegistry(apps)
        registry.create_queue("/fifo-closure", test_app, {"type": "string"}, {},
                              queue_type)

        server = MessageServer(11023, ApplicationRegistry(), registry,
                               SynonymRegistry(), event.set)
        thread = Thread(target=server.run)
        thread.start()
        event.wait()

        conn = WeaveConnection()
        conn.connect()

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
                except:
                    pass
            return run

        e1 = Event()
        r1 = Receiver(conn, "/fifo-closure", cookie=next(cookie))
        r1.start()
        patch_receive(r1, e1)
        t1 = Thread(target=wrap_run(r1))
        t1.start()

        e2 = Event()
        r2 = Receiver(conn, "/fifo-closure", cookie=next(cookie))
        r2.start()
        patch_receive(r2, e2)
        t2 = Thread(target=wrap_run(r2))
        t2.start()

        e1.wait()
        e2.wait()

        server.shutdown()
        thread.join()
        t1.join()
        t2.join()
