"""
Contains TileView class and TileViewWebSocket. Show apps/items in tiles.
"""
from .base_view import BaseViewWebSocket, BaseView

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
        self.view_args["tiles"] = tiles

