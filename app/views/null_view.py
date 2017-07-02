"""
Contains classes to use for empty view (empty HTML, no communications etc).
"""
from .base_view import BaseViewWebSocket, BaseView


class NullWebSocket(BaseViewWebSocket):
    def notify_updates(self):
        pass

class NullView(BaseView):
    """
    Empty View
    """

    def __init__(self, namespace, socketio, msg=""):
        super().__init__(NullWebSocket(self, namespace, socketio))
        self.msg = msg

    def html(self):
        return self.msg

