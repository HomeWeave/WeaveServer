"""
Contains TileView class and TileViewWebSocket. Show apps/items in tiles.
"""
from .base_view import BaseViewWebSocket, BaseView

def select_tile(tiles, index):
    for tile in tiles:
        tile["selected"] = False
    tiles[index]["selected"] = True


class TileViewWebSocket(BaseViewWebSocket):
    """Manages all the clients and responds with latest view in self.display"""

    def __init__(self, view, namespace, socketio):
        super(TileViewWebSocket, self).__init__(view, namespace, socketio)

class TileView(BaseView):
    """
    Displays items in tiles.
    """

    HTML = "tile.html"

    def __init__(self, namespace, socketio, tiles):
        sock = TileViewWebSocket(self, namespace, socketio)
        super().__init__(sock)
        self.tiles = tiles
        self.selected_tile_index = 0
        self.view_args["tiles"] = tiles
        select_tile(tiles, self.selected_tile_index)

    def on_command(self, command):
        if command == "LEFT":
            delta = -1
        elif command == "RIGHT":
            delta = 1
        else:
            raise ValueError
        self.selected_tile_index += len(self.tiles) + delta
        self.selected_tile_index %= len(self.tiles)
        select_tile(self.tiles, self.selected_tile_index)
        self.notify_updates()

        return True

