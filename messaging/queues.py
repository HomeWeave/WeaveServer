import json
import time
from collections import defaultdict

from jsonschema import validate

from weavelib.exceptions import AuthenticationFailed

from .messaging_utils import get_required_field


class BaseQueue(object):
    def __init__(self, queue_info):
        self.queue_info = queue_info

    def connect(self):
        return True

    def disconnect(self):
        return True

    def validate_schema(self, msg):
        validate(msg, self.queue_info.request_schema)

    def check_auth(self, task, headers):
        if not self.queue_info.force_auth:
            return

        # TODO: Clean this up. Use a separate extensible authorization module.
        if not headers.get("AUTH"):
            raise AuthenticationFailed("Invalid AUTH header.")

        if headers["AUTH"].get("type") == "SYSTEM":
            return

        appid = headers["AUTH"]["appid"]

        if self.queue_info.get("authorization") and\
                appid not in self.queue_info["authorization"]["auth_whitelist"]:
            raise AuthenticationFailed("Unauthorized.")

    def pack_message(self, task, headers):
        reqd = {"AUTH": json.dumps}
        headers = {x: f(headers[x]) for x, f in reqd.items() if x in headers}
        return {
            "task": task,
            "headers": headers
        }

    def unpack_message(self, obj):
        return obj["task"], obj["headers"]

    def __repr__(self):
        return (self.__class__.__name__ +
                "({})".format(self.queue_info.queue_name))


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

    def enqueue(self, task, headers):
        self.validate_schema(task)
        self.check_auth(task, headers)

        msg = self.pack_message(task, headers)
        msg.update(self.pack_attributes(task, headers))

        self.on_enqueue(msg)

        for requestor, out in self.current_requestors.items():
            value = self.dequeue_condition(requestor)
            if value:
                msg = self.on_dequeue(requestor, value)
                out(self.unpack_message(msg))

    def on_enqueue(self, msg):
        raise NotImplementedError

    def before_dequeue(self, requestor_id):
        pass

    def dequeue_condition(self, requestor_id):
        raise NotImplementedError

    def on_dequeue(self, requestor_id, condition_value):
        raise NotImplementedError

    def dequeue(self, headers, out):
        requestor_id = get_required_field(headers, self.REQUESTOR_ID_FIELD)
        self.check_auth(None, headers)

        self.current_requestors[requestor_id] = out
        self.before_dequeue(requestor_id)

        condition_value = self.dequeue_condition(requestor_id)
        if condition_value:
            msg = self.on_dequeue(requestor_id, condition_value)
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

    def on_enqueue(self, obj):
        self.latest_version += 1
        obj["version"] = self.latest_version
        self.messages.append(obj)

    def dequeue_condition(self, requestor_id):
        cur_version = self.requestor_version_map[requestor_id]
        for msg in self.messages:
            if msg["version"] <= cur_version:
                continue
            if msg["cookie"] == requestor_id:
                return msg
        return None

    def on_dequeue(self, requestor_id, condition_value):
        self.requestor_version_map[requestor_id] = condition_value["version"]
        return condition_value


class FIFOQueue(SynchronousQueue):
    def __init__(self, queue_info):
        super().__init__(queue_info)
        self.queue = []
        self.requestors = []

    def on_enqueue(self, obj):
        self.queue.append(obj)

    def dequeue_condition(self, requestor_id):
        return self.queue and self.requestors and \
               self.requestors[0] == requestor_id

    def before_dequeue(self, requestor_id):
        self.requestors.append(requestor_id)

    def on_dequeue(self, requestor_id, condition_value):
        self.requestors.pop(0)
        return self.queue.pop(0)
