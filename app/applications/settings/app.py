from app.core.base_app import BaseApp, BaseCommandsListener
from app.core.base_app import BaseWebSocket

class SettingsApp(BaseApp):
    ICON = "fa-cog"
    NAME = "Settings"
    DESCRIPTION = "Configure the system."

    def __init__(self, service, socketio):
        socket = BaseWebSocket("/app/settings", socketio)
        listener = BaseCommandsListener()
        super().__init__(socket, listener)

    def html(self):
        return "settings"

