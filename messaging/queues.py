import json
import time
from collections import defaultdict
from threading import RLock

from jsonschema import validate

from weavelib.exceptions import AuthenticationFailed, Unauthorized

from .messaging_utils import get_required_field
from .authorizers import AllowAllAuthorizer


class BaseChannel(object):
    def __init__(self, channel_info):
        self.channel_info = channel_info

    def connect(self):
        return True

    def disconnect(self):
        return True

    def validate_schema(self, msg):
        validate(msg, self.channel_info.request_schema)

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


class BaseQueue(BaseChannel):
    def pack_message(self, task, headers):
        reqd = {"AUTH": json.dumps}
        headers = {x: f(headers[x]) for x, f in reqd.items() if x in headers}
        return {
            "task": task,
            "headers": headers
        }

    def unpack_message(self, obj):
        return obj["task"], obj["headers"]


class SynchronousQueue(BaseQueue):
    REQUESTOR_ID_FIELD = "SESS"

    def __init__(self, queue_info):
        super().__init__(queue_info)
        self.active = False
        self.current_requestors = {}

    def connect(self):
        self.active = True
        return True

    def disconnect(self):
        self.active = False

    def pack_attributes(self, task, headers):
        return {}

    def push(self, task, headers):
        self.validate_schema(task)
        self.check_auth('push', headers)

        msg = self.pack_message(task, headers)
        msg.update(self.pack_attributes(task, headers))

        self.on_push(msg)

        for requestor, out in self.current_requestors.items():
            value = self.pop_condition(requestor)
            if value:
                msg = self.on_pop(requestor, value)
                out(self.unpack_message(msg))

    def on_push(self, msg):
        raise NotImplementedError

    def before_pop(self, requestor_id):
        pass

    def pop_condition(self, requestor_id):
        raise NotImplementedError

    def on_pop(self, requestor_id, condition_value):
        raise NotImplementedError

    def pop(self, headers, out):
        requestor_id = get_required_field(headers, self.REQUESTOR_ID_FIELD)
        self.check_auth('pop', headers)

        self.current_requestors[requestor_id] = out
        self.before_pop(requestor_id)

        condition_value = self.pop_condition(requestor_id)
        if condition_value:
            msg = self.on_pop(requestor_id, condition_value)
            out(self.unpack_message(msg))


class SessionizedQueue(SynchronousQueue):
    REQUESTOR_ID_FIELD = "COOKIE"

    def __init__(self, queue_info):
        super().__init__(queue_info)
        self.requestor_version_map = defaultdict(int)
        self.latest_version = 1
        self.messages = []

    def pack_attributes(self, task, headers):
        return {
            "cookie": get_required_field(headers, "COOKIE"),
            "time": time.time()
        }

    def on_push(self, obj):
        self.latest_version += 1
        obj["version"] = self.latest_version
        self.messages.append(obj)

    def pop_condition(self, requestor_id):
        cur_version = self.requestor_version_map[requestor_id]
        for msg in self.messages:
            if msg["version"] <= cur_version:
                continue
            if msg["cookie"] == requestor_id:
                return msg
        return None

    def on_pop(self, requestor_id, condition_value):
        self.requestor_version_map[requestor_id] = condition_value["version"]
        return condition_value


class FIFOQueue(SynchronousQueue):
    def __init__(self, queue_info):
        super().__init__(queue_info)
        self.queue = []
        self.requestors = []

    def on_push(self, obj):
        self.queue.append(obj)

    def pop_condition(self, requestor_id):
        return self.queue and self.requestors and \
               self.requestors[0] == requestor_id

    def before_pop(self, requestor_id):
        self.requestors.append(requestor_id)

    def on_pop(self, requestor_id, condition_value):
        self.requestors.pop(0)
        return self.queue.pop(0)


class Multicast(BaseChannel):
    def __init__(self, multicast_info):
        super().__init__(multicast_info)
        self.active = False
        self.requestors = {}
        self.requestors_lock = RLock()

    def connect(self):
        self.active = True
        return True

    def disconnect(self):
        self.active = False

    def push(self, task, headers):
        self.validate_schema(task)
        self.check_auth('push', headers)
        current_requestor = get_required_field(headers, 'SESS')

        with self.requestors_lock:
            requestors = list(self.requestors.items())

        for requestor_id, out_fn in requestors:
            if requestor_id != current_requestor:
                out_fn((task, headers))

    def pop(self, headers, out_fn):
        requestor_id = get_required_field(headers, 'SESS')
        self.check_auth('pop', headers)

        with self.requestors_lock:
            self.requestors[requestor_id] = out_fn
