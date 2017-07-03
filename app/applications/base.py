"""
Subclass BaseApplication for all the apps.
"""


class BaseApplication(object):
    """
    Represents the basic properties/functionalities of an app.
    """

    ICON = "fa-pencil-square-o"
    NAME = ""
    DESCRIPTION = ""

    def __init__(self, service, socketio, view):
        self.service = service
        self.socketio = socketio
        self._view = view

    def name(self):
        return self.NAME or self.__class__.__name__

    def icon(self):
        return self.ICON

    def description(self):
        return self.DESCRIPTION or ""

    def view(self):
        return self._view

    def on_command(self, command):
        # Pass all commands apps receive to the view.
        try:
            self._view.on_command(command)
        except ValueError:
            self.handle_command(command)

    def handle_command(self, command):
        pass
