import json
from collections import defaultdict
from threading import Lock

from jsonschema import validate, ValidationError

from weavelib.exceptions import AuthenticationFailed, Unauthorized
from weavelib.exceptions import SchemaValidationFailed

from .messaging_utils import get_required_field
from .authorizers import AllowAllAuthorizer


def filter_headers(headers, fields):
    return {k: v for k, v in headers.items() if k.upper() in fields}


class BaseChannel(object):
    def __init__(self, channel_info):
        self.channel_info = channel_info

    def connect(self):
        return True

    def disconnect(self):
        return True

    def validate_schema(self, msg):
        try:
            validate(msg.task, self.channel_info.request_schema)
        except ValidationError:
            msg = "Schema: {}, on instance: {}, for channel: {}".format(
                self.channel_info.request_schema, msg.task, self)
            raise SchemaValidationFailed(msg)

    def check_auth(self, op, headers):
        authorizer = self.channel_info.authorizers.get(op, AllowAllAuthorizer())

        # headers.get("AUTH") == ApplicationRegistry.get_app_info().
        app_info = headers.get("AUTH", {})

        default_app_url = object()
        app_url = app_info.get("app_url", default_app_url)
        res = authorizer.authorize(app_url, op, self.channel_info.channel_name)
        if not res:
            if app_url is default_app_url:
                raise AuthenticationFailed()
            raise Unauthorized("Action is not authorized.")

    def __repr__(self):
        return (self.__class__.__name__ +
                "({})".format(self.channel_info.channel_name))


class SynchronousQueue(BaseChannel):
    def __init__(self, queue_info):
        super().__init__(queue_info)
        self.active = False

    def connect(self):
        self.active = True
        return True

    def disconnect(self):
        self.active = False

    def push(self, msg):
        self.validate_schema(msg)
        self.check_auth('push', msg.headers)
        self.on_push(msg)

    def on_push(self, msg):
        raise NotImplementedError

    def pop(self, msg, out):
        self.check_auth('pop', msg.headers)

        def post_process_out_message(task, headers):
            if "AUTH" in headers:
                headers["AUTH"] = json.dumps(headers["AUTH"])
            out(task, headers)

        self.on_pop(msg, post_process_out_message)

    def on_pop(self, dequeue_msg, out):
        raise NotImplementedError

    def remove_requestor(self, requestor_id):
        raise NotImplementedError


# TODO: Handle case when there's an IOError when writing the msg out.


class RoundRobinQueue(SynchronousQueue):
    def __init__(self, queue_info):
        super().__init__(queue_info)
        self.retain_headers = {"AUTH"}
        self.queue = []
        self.requestors = []
        self.requestors_by_session_id = {}
        self.lock = Lock()

    def on_push(self, obj):
        active_pop_requestor = None
        with self.lock:
            if self.requestors:
                active_pop_requestor = self.requestors.pop(0)
            else:
                self.queue.append(obj)

        if active_pop_requestor:
            headers = filter_headers(obj.headers, self.retain_headers)
            active_pop_requestor(obj.task, headers)

    def on_pop(self, dequeue_msg, out):
        with self.lock:
            if self.queue:
                msg = self.queue.pop(0)
            else:
                msg = None
                self.requestors.append(out)
                self.requestors_by_session_id[dequeue_msg.headers["SESS"]] = out

        if msg:
            out(msg.task, filter_headers(msg.headers, self.retain_headers))
            return True
        return False

    def get_queue_size(self):
        with self.lock:
            return len(self.queue)

    def get_requestors_size(self):
        with self.lock:
            return len(self.requestors)

    def remove_requestor(self, session_id):
        with self.lock:
            requestor = self.requestors_by_session_id.pop(session_id, None)
            if requestor:
                self.requestors.remove(requestor)


class SessionizedQueue(SynchronousQueue):
    REQUESTOR_ID_FIELD = "COOKIE"

    def __init__(self, queue_info):
        super().__init__(queue_info)

        def new_fifo_queue():
            queue = RoundRobinQueue(queue_info)
            queue.connect()
            return queue

        self.queues = defaultdict(new_fifo_queue)
        self.session_id_to_cookie_map = {}
        self.lock = Lock()

    def on_push(self, msg):
        cookie = get_required_field(msg.headers, "COOKIE")
        with self.lock:
            queue = self.queues[cookie]
        queue.on_push(msg)

    def on_pop(self, dequeue_msg, out):
        cookie = get_required_field(dequeue_msg.headers, "COOKIE")
        with self.lock:
            queue = self.queues[cookie]

        item_was_popped = queue.on_pop(dequeue_msg, out)

        with self.lock:
            if not item_was_popped:
                session_id = dequeue_msg.headers["SESS"]
                self.session_id_to_cookie_map[session_id] = cookie

        with self.lock:
            if not queue.get_queue_size() and not queue.get_requestors_size():
                self.queues.pop(cookie)

    def remove_requestor(self, session_id):
        with self.lock:
            cookie = self.session_id_to_cookie_map.pop(session_id, None)
            self.queues[cookie].remove_requestor(session_id)


class Multicast(SynchronousQueue):
    def __init__(self, multicast_info):
        super().__init__(multicast_info)
        self.active = False
        self.requestors = {}
        self.lock = Lock()

    def on_push(self, msg):
        current_requestor = get_required_field(msg.headers, 'SESS')

        with self.lock:
            requestors = list(self.requestors.items())

        for requestor_id, out_fn in requestors:
            if requestor_id != current_requestor:
                out_fn(msg.task, filter_headers(msg.headers, {"AUTH"}))

    def pop(self, dequeue_msg, out_fn):
        requestor_id = get_required_field(dequeue_msg.headers, 'SESS')
        self.check_auth('pop', dequeue_msg.headers)

        with self.lock:
            self.requestors[requestor_id] = out_fn
