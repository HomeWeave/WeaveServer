from app.views import SimpleHeaderView
from app.applications.base import BaseApplication


class WifiApp(BaseApplication):
    NAME = "WiFi"
    ICON = "fa-wifi"
    DESCRIPTION = "Connect to Wifi network"

    NAMESPACE = "/app/WifiApp"

    def __init__(self, service, socketio):
        view = SimpleHeaderView(self.NAMESPACE, socketio, "Wifi")
        super().__init__(service, socketio, view)

