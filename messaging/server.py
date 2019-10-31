import logging
try:
    from queue import Queue
except ImportError:
    from Queue import Queue
import socket
from socketserver import ThreadingTCPServer, StreamRequestHandler
from threading import RLock, Thread


from weavelib.exceptions import WeaveException, ObjectNotFound
from weavelib.exceptions import AuthenticationFailed
from weavelib.exceptions import ProtocolError, BadOperation
from weavelib.messaging import read_message, serialize_message, Message
from weavelib.messaging import exception_to_message

from .messaging_utils import get_required_field


logger = logging.getLogger(__name__)


class MessageHandler(StreamRequestHandler):
    def handle(self):
        response_queue = Queue()
        thread = Thread(target=self.process_queue, args=(response_queue,))
        thread.start()

        conn = Connection(self.request, self.rfile, self.wfile)
        self.server.add_connection(conn)

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
            self.server.remove_connection(conn)

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


class Connection(object):
    def __init__(self, sock, rfile, wfile):
        self.sock = sock
        self.rfile = rfile
        self.wfile = wfile

    def __hash__(self):
        return hash(self.sock.fileno())

    def __eq__(self, other):
        return self.sock.fileno() == other.sock.fileno()

    def close(self):
        def safe_close(obj):
            try:
                obj.close()
            except (IOError, OSError):
                pass

        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except (IOError, OSError):
            pass
        safe_close(self.sock)
        safe_close(self.rfile)
        safe_close(self.wfile)


class MessageServer(ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, port, apps_registry, channel_registry, synonym_registry,
                 notify_start):
        super().__init__(("", port), MessageHandler)
        self.notify_start = notify_start
        self.sent_start_notification = False
        self.channel_registry = channel_registry
        self.apps_registry = apps_registry
        self.synonym_registry = synonym_registry
        self.active_connections = set()
        self.active_connections_lock = RLock()

    def handle_message(self, msg, out_queue):
        session_id = get_required_field(msg.headers, "SESS")
        channel_name = get_required_field(msg.headers, "C")
        channel_name = self.synonym_registry.translate(channel_name)
        channel = self.channel_registry.get_channel(channel_name)

        self.preprocess(msg)

        def handle_pop(task, headers):
            msg = Message("inform", task)
            msg.headers.update(headers)
            msg.headers["SESS"] = session_id
            out_queue.put(msg)

        if msg.operation == "pop":
            channel.pop(msg, handle_pop)
        elif msg.operation == "push":
            if msg.task is None:
                raise ProtocolError("Task is required for push.")

            channel.push(msg)

            msg = Message("result")
            msg.headers["RES"] = "OK"
            msg.headers["SESS"] = session_id
            out_queue.put(msg)
        else:
            raise BadOperation(msg.operation)

    def preprocess(self, msg):
        if "AUTH" in msg.headers:
            app_token = msg.headers["AUTH"]
            try:
                msg.headers["AUTH"] = self.apps_registry.get_app_info(app_token)
            except ObjectNotFound:
                raise AuthenticationFailed()

    def run(self):
        self.serve_forever()

    def service_actions(self):
        if not self.sent_start_notification:
            self.notify_start()
            self.sent_start_notification = True

    def add_connection(self, conn):
        with self.active_connections_lock:
            self.active_connections.add(conn)

    def remove_connection(self, conn):
        with self.active_connections_lock:
            self.active_connections.remove(conn)

    def shutdown(self):
        self.channel_registry.shutdown()

        with self.active_connections_lock:
            for conn in self.active_connections:
                conn.close()

        super().shutdown()
        super().server_close()
