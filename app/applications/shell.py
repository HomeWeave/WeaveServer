import logging

from app.views import TileView
from app.applications import APPS
from .base import BaseApplication


logger = logging.getLogger(__name__)

def build_tile_info(application):
    return {
        "name": application.name(),
        "icon": application.icon(),
        "description": application.description(),
    }

class ShellApp(BaseApplication):

    NAMESPACE = "/app/ShellApp"

    def __init__(self, service, socketio, apps):
        self.apps = apps
        self.apps_map = {app.name(): app for app in self.apps}
        tiles = [build_tile_info(app) for app in self.apps]
        self.tile_view = TileView(self.NAMESPACE, socketio, tiles)
        super().__init__(service, socketio, self.tile_view)

    def handle_command(self, command):
        if command == "CLICK":
            tile = self.tile_view.get_selected_tile()
            app = self.apps_map[tile["name"]]
            self.service.launch_app(app)

