"""
Exposes SimpleHeaderView that is a simple HTML view with <h1> and <h3>
"""
from .base_view import BaseView, BaseViewWebSocket


class SimpleViewWebSocket(BaseViewWebSocket):
    pass


class SimpleHeaderView(BaseView):
    """
    A simple HTML view with msg show within <h1>.
    """
    HTML_PATH = "simple.html"

    def __init__(self, namespace, socketio, msg):
        sock = SimpleViewWebSocket(self, namespace, socketio)
        super().__init__(sock)
        self.view_args["title"] = msg


