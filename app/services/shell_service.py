"""
Exposes ShellService which has a purpose similar to a shell.
"""

from threading import Event
import time

import eventlet

from app.core.remotecontrol import RemoteControlServer, CommandsTranslator
from app.views.root_view import RootView
from app.views.wrapper_view import WrapperView
from app.views.null_view import NullView
from app.applications import APPS
from app.applications.shell import ShellApp
from .base import BaseService, BlockingServiceStart


class ShellService(BaseService, BlockingServiceStart):
    """ A basic shell. """

    NAMESPACE = "/shell"

    def __init__(self, socketio):
        self.socketio = socketio
        self.apps = [app(self, socketio) for app in APPS]
        self.apps_stack = [ShellApp(self, socketio, self.apps)]
        self.quit_event = Event()
        view, self.centre_view, self.top_view = self.build_view(socketio)
        super().__init__(view=view)

        translator = CommandsTranslator(self)
        self.remote_control = RemoteControlServer(translator)


    def build_view(self, socketio):
        top_view = NullView(self.NAMESPACE + "/top", socketio, msg="Top bar")
        front_app = self.apps_stack[-1]
        center_view = WrapperView(self.NAMESPACE + "/center", socketio, front_app.view())
        root_view = RootView(self.NAMESPACE, socketio, center_view, top_view)
        return root_view, center_view, top_view

    def on_service_start(self, *args, **kwargs):
        self.apps_stack[0].start()
        eventlet.spawn(self.remote_control.serve_forever)
        Event().wait()

    def on_command(self, command):
        return "OK" if self.apps_stack[-1].on_command(command) else "BAD"

    def launch_app(self, app):
        old_front_app = self.apps_stack[-1]
        new_front_app = app
        self.apps_stack.append(app)
        self.replace_app(old_front_app, new_front_app)

    def exit_app(self, app):
        old_front_app = self.apps_stack[-1]
        if app is not old_front_app:
            return False

        if len(self.apps_stack) <= 1:
            return False #Can't exit ShellApp

        new_front_app = self.apps_stack[-2]
        del self.apps_stack[-1]
        self.replace_app(old_front_app, new_front_app)

    def replace_app(self, old_front_app, new_front_app):
        #Unregister old_front_app, and register new_front_app
        for sock in old_front_app.view().get_sockets():
            self.socketio.unregister(sock)
        self.centre_view.set_wrapped_view(new_front_app.view())
        for sock in new_front_app.view().get_sockets():
            self.socketio.register(sock)
        self.centre_view.notify_updates()

        new_front_app.start()


