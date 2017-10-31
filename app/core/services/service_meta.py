import logging
from copy import deepcopy
from threading import Thread
from uuid import uuid4

from jsonschema import validate, ValidationError

from app.core.messaging import Message, Creator, Receiver, Sender


logger = logging.getLogger(__name__)


def create_capabilities_queue(queue_name):
    queue_info = {
        "queue_name":queue_name,
        "queue_type": "keyedsticky",
        "request_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
                "params": {"type": "object"},
                "id": {"type": "string"},
            }
        }
    }
    creator = Creator()
    creator.start()
    creator.create(queue_info)


class Capability(Message):
    def __init__(self, name, description, params):
        self.uuid = str(uuid4())
        self.params = deepcopy(params)
        obj = {
            "name": name,
            "description": description,
            "params": self.params,
            "id": self.uuid,
        }
        super().__init__("enqueue", obj)

    @property
    def unique_id(self):
        return self.uuid

    @property
    def parameters(self):
        return self.params

    @property
    def schema(self):
        return {
            "type": "object",
            "properties": self.params,
            "required": list(self.params.keys())
        }


class EventReceiver(Receiver):
    def __init__(self, queue_name, capability, handler):
        super().__init__(queue_name)
        self.capability = capability
        self.handler = handler

    def on_message(self, msg):
        try:
            validate(msg, self.capability.schema)
        except ValidationError:
            logger.warning("Failed EventReceiver schema validation: %s", msg)
            return

        self.handler(**msg)


class EventDrivenService(object):
    def express_capability(self, capability, handler):
        if not hasattr(self, 'event_driven_intialized'):
            self.initialize_event_driven_service()

        queue_name = self.get_service_queue_name("capabilities")
        capability_sender = Sender(queue_name)
        capability_sender.start()
        headers = {"KEY": capability.unique_id}
        capability_sender.send(capability, headers=headers)

        self.create_event_queue(capability)
        self.start_event_receiver(queue_name, capability, handler)

    def initialize_event_driven_service(self):
        create_capabilities_queue(self.get_service_queue_name("capabilities"))

    def create_event_queue(self, capability):
        qid = capability.unique_id
        queue_name = self.get_service_queue_name("capability/" + qid)
        queue_info = {
            "queue_name": queue_name,
            "request_schema": capability.schema
        }
        creator = Creator()
        creator.start()
        creator.create(queue_info)

    def start_event_receiver(self, queue_name, capability, handler):
        params = (queue_name, capability, handler)
        thread = Thread(target=self.run_event_receiver, args=params)
        thread.start()
        return thread

    def run_event_receiver(self, queue_name, capability, handler):
        receiver = EventReceiver(queue_name, capability, handler)
        receiver.start()
        receiver.run()

    def get_service_queue_name(self, queue_name):
        service_name = self.get_component_name()
        return "/services/{}/{}".format(service_name, queue_name)
