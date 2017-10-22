from uuid import uuid4

from app.core.messaging import Message


class Event(Message):
    def __init__(self, name):
        self.uuid = str(uuid4())
        obj = {
            "name": name,
            "id": self.uuid,
        }
        super().__init__("enqueue", obj)

    def unique_id(self):
        return self.uuid


class Capability(Message):
    def __init__(self, name, description):
        self.uuid = str(uuid4())
        obj = {
            "name": name,
            "description": description,
            "id": self.uuid,
        }
        super().__init__("enqueue", obj)
