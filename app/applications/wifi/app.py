from app.core.base_app import BaseApp, BaseCommandsListener
from app.core.base_app import BaseWebSocket


class WifiApp(BaseApp):
    NAME = "WiFi"
    ICON = "fa-wifi"
    DESCRIPTION = "Connect to Wifi network"

    def __init__(self, service, socketio):
        socket = BaseWebSocket("/app/wifi", socketio)
        listener = BaseCommandsListener()
        super().__init__(socket, listener)

