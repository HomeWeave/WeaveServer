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

    def start(self):
        pass

    def on_command(self, command):
        # Pass all commands apps receive to the view.
        chain = [self._view.on_command, self.handle_command]
        for item in chain:
            if item(command):
                return True

    def handle_command(self, command):
        if command == "BACK":
            self.service.exit_app(self)
            return True

