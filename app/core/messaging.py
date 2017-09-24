import json
import logging
import socket

from retask import Task


logger = logging.getLogger(__name__)

def parse_message(lines):
    required_fields = {"OP", "Q"}
    fields = {}
    for line in lines:
        line_parts = line.split(" ", 1)
        fields[line_parts[0]] = line_parts[1]

    if required_fields - set(fields.keys()):
        logger.info("Invalid: %s: ", lines)
        raise InvalidMessageStructure

    if "MSG" in fields:
        obj = json.loads(fields["MSG"])
        task = Task(obj)
    else:
        task = None
    return Message(fields["OP"], fields["Q"], task)


def serialize_message(msg):
    msg_lines = [
        "OP " + msg.op,
        "Q " + msg.target,
    ]
    if msg.task is not None:
        msg_lines.append("MSG " + json.dumps(msg.task.data))
    msg_lines.append("")  # Last newline before blank line.
    return "\n".join(msg_lines)


def read_message(conn):
    # Reading group of lines
    lines = []
    line_read = False
    while True:
        line = conn.readline()
        stripped_line = line.strip()
        if not line:
            return None
        if not stripped_line:
            break
        lines.append(stripped_line.decode("UTF-8"))
        line_read = True
    return parse_message(lines)


def write_message(conn, msg):
    conn.write((serialize_message(msg) + "\n").encode())
    conn.flush()

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


class Sender(object):
    PORT = 11023
    READ_BUF_SIZE = -1
    WRITE_BUG_SIZE = 10240

    def __init__(self, queue, host="localhost"):
        self.queue = queue
        self.host = host
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def start(self):
        self.sock.connect((self.host, self.PORT))
        self.rfile = self.sock.makefile('rb', self.READ_BUF_SIZE)
        self.wfile = self.sock.makefile('wb', self.WRITE_BUG_SIZE)

    def send(self, obj):
        msg = Message("enqueue", self.queue, obj)
        write_message(self.wfile, msg)
        self.wfile.flush()


class Receiver(object):
    PORT = 11023
    READ_BUF_SIZE = -1
    WRITE_BUG_SIZE = 10240

    def __init__(self, queue, host="localhost"):
        self.queue = queue
        self.host = host
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.active = False

    def run(self, on_start=None):
        self.sock.connect((self.host, self.PORT))
        rfile = self.sock.makefile('rb', self.READ_BUF_SIZE)
        wfile = self.sock.makefile('wb', self.WRITE_BUG_SIZE)
        if on_start is not None:
            on_start()
        self.active = True

        dequeue_msg = Message("dequeue", self.queue)
        write_message(wfile, dequeue_msg)
        while self.active:
            msg = read_message(rfile)
            if msg is None:
                break

            if msg.task is not None:
                self.on_message(msg.task.data)
            else:
                logger.warning("Dropping message without data.")
                continue

            # TODO: ACK the server.
        rfile.close()
        wfile.close()
        self.sock.close()

    def stop(self):
        self.active = False

    def on_message(self, msg):
        pass
