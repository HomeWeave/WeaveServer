"""
Exposes ShellService which has a purpose similar to a shell.
"""

from threading import Event
import time

import gevent

from app.core.remotecontrol import RemoteControlServer, CommandsTranslator
from app.views.root_view import RootView
from app.views.tile_view import TileView
from app.views.null_view import NullView
from app.applications import APPS
from .base import BaseService, BlockingServiceStart


def build_tile_info(application):
    return {
        "name": application.name(),
        "icon": application.icon(),
        "description": application.description(),
    }

class ShellService(BaseService, BlockingServiceStart):
    """ A basic shell. """

    NAMESPACE = "/shell"

    def __init__(self, socketio):
        self.apps = [app() for app in APPS]
        view = self.build_view(socketio)
        super().__init__(view=view)

        self.app_stack = []
        self.quit_event = Event()
        self.remote_control = RemoteControlServer(self)
        self.translator = CommandsTranslator()


    def build_view(self, socketio):
        top_view = NullView(self.NAMESPACE + "/top", socketio, msg="Top bar")
        tiles = [build_tile_info(app) for app in self.apps]
        center_view = TileView(self.NAMESPACE + "/center", socketio, tiles)
        root_view = RootView(self.NAMESPACE, socketio, center_view, top_view)
        return root_view

    def on_service_start(self, *args, **kwargs):
        gevent.spawn(self.remote_control.serve_forever)
        self.quit_event.wait()

    def on_command(self, command_id):
        command = self.translator.translate_command(command_id)

