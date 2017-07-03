from app.views import TileView
from app.applications import APPS
from .base import BaseApplication

def build_tile_info(application):
    return {
        "name": application.name(),
        "icon": application.icon(),
        "description": application.description(),
    }

class ShellApp(BaseApplication):

    NAMESPACE = "/app/ShellApp"

    def __init__(self, service, socketio, apps):
        self.apps = [app(service, socketio) for app in APPS]
        tiles = [build_tile_info(app) for app in self.apps]
        view = TileView(self.NAMESPACE, socketio, tiles)
        super().__init__(service, socketio, view)

