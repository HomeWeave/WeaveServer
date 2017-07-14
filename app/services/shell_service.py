"""
Exposes ShellService which has a purpose similar to a shell.
"""


import eventlet
from eventlet.event import Event

from app.core.remotecontrol import CommandsTranslator
from app.core.base_app import BaseCommandsListener
from app.core.base_app import BaseWebSocket
from app.applications import APPS
from app.applications import ShellApp
from .base import BaseService, BlockingServiceStart


def build_app_info(app):
    return {
        "id": app.name(),
        "name": app.name(),
        "html": app.html(),
        "namespace": app.get_namespace()
    }

class ShellBackgroundCommandsListener(BaseCommandsListener):
    COMMANDS = [
        {"name": "Exit"},
        {"name": "Home"},
        {"name": "Restart"}
    ]

    def __init__(self, service):
        self.service = service
        super().__init__()

    def on_command(self, command):
        if command == "Exit":
            self.service.exit_app()
            return "OK"
        elif command == "Home":
            self.service.switch(0)
            return "Ok"

    def list_commands(self):
        return self.COMMANDS


class ShellServiceWebSocket(BaseWebSocket):
    def __init__(self, service, socketio):
        super().__init__("/shell", socketio)
        self.service = service

    def notify_launch_app(self, app):
        self.reply_all('launch', app.name())

    def notify_switch_app(self, app):
        self.reply_all('switch', app.name())

    def on_get_active_apps(self, *args):
        res = {
            "apps": self.service.get_active_apps(),
            "activeAppId": self.service.apps_stack[-1].name()
        }
        self.reply_all('active_apps', res)

class ShellService(BaseService, BlockingServiceStart):
    """ A basic shell. """

    def __init__(self, socketio):
        super().__init__()
        self.socketio = socketio

        self.main_socket = ShellServiceWebSocket(self, socketio)
        socketio.register(self.main_socket)

        self.apps = [cls(self, socketio) for cls in APPS]
        self.shell_app = ShellApp(self, self.apps, socketio)
        self.apps_stack = [self.shell_app]

        self.listener = ShellBackgroundCommandsListener(self)
        self.translator = CommandsTranslator(self)


    def on_service_start(self, *args, **kwargs):
        self.launch_app(self.shell_app)

        eventlet.spawn(self.translator.start)
        Event().wait()

    def on_command(self, command):
        res = self.listener.on_command(command)
        if res is not None:
            return res

        return self.apps_stack[-1].on_command(command)

    def list_commands(self):
        yield from self.listener.list_commands()
        if self.apps_stack:
            yield from self.apps_stack[-1].list_commands()

    def get_active_apps(self):
        return [build_app_info(app) for app in self.apps_stack]

    def launch_app(self, app):
        # Todo: Perhaps "pause" old front app?
        # Todo: Check if its already in the apps_stack.

        new_front_app = app
        self.apps_stack.append(app)

        for sock in new_front_app.get_sockets():
            self.socketio.register(sock)

        new_front_app.start()

        self.main_socket.notify_launch_app(new_front_app)

    def exit_app(self):
        old_front_app = self.apps_stack[-1]

        #Can't exit ShellApp
        if old_front_app is self.shell_app:
            return False

        old_front_app.stop()

        new_front_app = self.apps_stack[-2]

        del self.apps_stack[-1]

        #Unregister old_front_app, and register new_front_app
        for sock in old_front_app.get_sockets():
            self.socketio.unregister(sock)

        self.main_socket.notify_switch_app(new_front_app)
