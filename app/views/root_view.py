"""
Contains classes that handles root view -- ShellService
"""
from .base_view import BaseViewWebSocket, BaseView

class RootViewWebSocket(BaseViewWebSocket):
    """Manages all the clients and responds with latest view in self.display"""

    NAMESPACE = "/root"

    def __init__(self, view, socketio):
        super(RootViewWebSocket, self).__init__(view, self.NAMESPACE, socketio)

class RootView(BaseView):
    pass


