"""
Contains classes that handles root view -- ShellService
"""
from .base_view import BaseViewWebSocket, BaseView

class RootViewWebSocket(BaseViewWebSocket):
    """Manages all the clients and responds with latest view in self.display"""

    def __init__(self, view, namespace, socketio):
        super(RootViewWebSocket, self).__init__(view, namespace, socketio)

class RootView(BaseView):
    """ Outermost view for the shell. """

    HTML = "shell.html"

    def __init__(self, namespace, socketio, centre_view, top_view):
        main_socket = RootViewWebSocket(self, namespace, socketio)
        super().__init__(main_socket)
        self.centre_view = centre_view
        self.top_view = top_view

        self.add_inner_view('centre_view', centre_view)
        self.add_inner_view('top_view', top_view)


