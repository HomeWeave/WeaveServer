"""
This module helps translate commands into UUIDs and back. We need this so that
clients do not work off stale views. Ideally, the refresh operation needs to occur
every time a view changes.
"""

from uuid import uuid4


STANDARD_ACTIONS = ["LEFT", "RIGHT", "CLICK"]

class CommandsTranslator(object):
    def __init__(self, service, actions=None):
        self.service = service
        self._actions = actions or STANDARD_ACTIONS
        self.refresh()

    def translate_command(self, command_id):
        return self.map.get(command_id)

    def refresh(self):
        self.map = CommandsTranslator.build_new_map(self._actions)

    @property
    def actions(self):
        return self._actions

    @actions.setter
    def actions(self, val):
        self._actions = val
        self.refresh()

    @staticmethod
    def build_new_map(actions):
        return {str(uuid4()): action for action in actions}

    def on_command(self, command_id):
        command = self.translate_command(command_id)
        if command is None:
            return "BAD"
        return "OK" if self.service.on_command(command) else "BAD"

    def get_controls(self):
        res = []
        for cid, name in self.map.items():
            obj = {"name": name, "id": cid}
            res.append(obj)

        return res

