from app.views import SimpleHeaderView
from app.applications.base import BaseApplication

class BluetoothApp(BaseApplication):
    ICON = "fa-bluetooth"
    NAME = "Bluetooth"
    DESCRIPTION = "Connect to Bluetooth devices."

    NAMESPACE = "/app/BluetoothApp"

    def __init__(self, service, socketio):
        view = SimpleHeaderView(self.NAMESPACE, socketio, "Bluetooth")
        super().__init__(service, socketio, view)

