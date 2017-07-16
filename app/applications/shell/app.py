import logging

from app.core.base_app import BaseApp, BaseCommandsListener
from app.core.base_app import BaseWebSocket


logger = logging.getLogger(__name__)

def build_tile_info(application):
    return {
        "id": application.id(),
        "name": application.name(),
        "icon": application.icon(),
        "description": application.description(),
    }

def select_tile(tiles, index):
    for tile in tiles:
        tile["selected"] = False
    tiles[index]["selected"] = True



class ShellCommandListener(BaseCommandsListener):
    COMMANDS = [
        {
            "name": "Left",
            "cmd": "left"
        },
        {
            "name": "Right",
            "cmd": "right"
        },
        {
            "name": "Click",
            "cmd": "click"
        }
    ]

    def __init__(self, app):
        self.app = app

    def on_command(self, command):
        func = getattr(self.app, "handle_" + command.lower(), None)
        if func is None:
            return None
        func()
        return "OK"

    def list_commands(self):
        return self.COMMANDS


class ShellWebSocket(BaseWebSocket):
    def __init__(self, app, socketio, namespace="/app/shell"):
        self.app = app
        super().__init__(namespace, socketio)

    def on_get_apps(self, *args):
        self.reply('apps', {"tiles": self.app.tiles})

    def notify_select(self, appId):
        self.reply_all('selected', {"appId": appId})

class ShellApp(BaseApp):
    def __init__(self, service, apps, socketio):
        self.socket = ShellWebSocket(self, socketio)
        self.cmd_listener = ShellCommandListener(self)
        super().__init__(self.socket, self.cmd_listener)

        self.service = service

        self.apps = apps
        self.apps_map = {app.id(): app for app in self.apps}

        self.selected_index = 0
        self.tiles = [build_tile_info(x) for x in self.apps]
        select_tile(self.tiles, self.selected_index)

    def html(self):
        with open(self.get_file("static/index.html")) as inp:
            return inp.read()

    def handle_click(self):
        tile = self.tiles[self.selected_index]
        app = self.apps_map[tile["id"]]
        self.service.launch_app(app)

    def handle_left(self):
        self.selected_index += len(self.tiles) - 1
        self.selected_index %= len(self.tiles)
        tile = self.tiles[self.selected_index]
        self.socket.notify_select(tile["id"])

    def handle_right(self):
        self.selected_index += len(self.tiles) + 1
        self.selected_index %= len(self.tiles)
        tile = self.tiles[self.selected_index]
        self.socket.notify_select(tile["id"])

    def on_command(self, command):
        self.cmd_listener.on_command(command)

    def list_commands(self):
        return self.cmd_listener.list_commands()

