from app.core.base_app import BaseApp, BaseCommandsListener
from app.core.base_app import BaseWebSocket

class BluetoothApp(BaseApp):
    ICON = "fa-bluetooth"
    NAME = "Bluetooth"
    DESCRIPTION = "Connect to Bluetooth devices."

    def __init__(self, service, socketio):
        socket = BaseWebSocket("/app/bluetooth", socketio)
        listener = BaseCommandsListener()
        super().__init__(socket, listener)

