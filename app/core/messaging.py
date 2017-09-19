import json
import socket

from retask import Task


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


def read_message(conn):
    # Reading group of lines
    lines = []
    line_read = False
    while True:
        line = conn.readline().strip()
        if line:
            lines.append(line.decode("UTF-8"))
            line_read = True
        else:
            break

        if not line_read:
            break
    return parse_message(lines)


def write_message(conn, msg):
    msg_lines = [
        "OP " + msg.op,
        "Q " + msg.target,
    ]
    if msg.task is not None:
        msg_lines.append("MSG " + msg.task)
    msg_lines.append("\n")  # Last blank line.
    conn.write("\n".join(msg_lines).encode())
    logger.info("\n".join(msg_lines).encode())
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
        logger.info("Connecting to: %s", (self.host, self.PORT))
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
            self.on_message(msg.task)

            # TODO: ACK the server.
        rfile.close()
        wfile.close()
        self.sock.close()

    def stop(self):
        self.active = False

    def on_message(self, msg):
        pass
