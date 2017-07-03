"""
Wrapper view is much like an iframe.
"""

from .base_view import BaseViewWebSocket, BaseView


class WrapperWebSocket(BaseViewWebSocket):
    def create_update_data(self):
        """
        For a WrapperView, force full data to be sent.
        """
        return self.create_full_data()

class WrapperView(BaseView):
    """
    Wraps an inner view.
    """

    def __init__(self, namespace, socketio, view):
        main_socket = WrapperWebSocket(self, namespace, socketio)
        super().__init__(main_socket)

        self.wrapped_view = view
        if view is not None:
            self.add_inner_view("wrapped_view", view)

    def set_wrapped_view(self, view):
        self.wrapped_view = view
        self.notify_updates()

    def html(self):
        return "{{{wrapped_view}}}" if self.wrapped_view is not None else ""

