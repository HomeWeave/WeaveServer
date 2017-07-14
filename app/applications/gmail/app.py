from app.core.base_app import BaseApp, BaseCommandsListener
from app.core.base_app import BaseWebSocket

class GmailApp(BaseApp):
    ICON = "fa-envelope"
    NAME = "Gmail"
    DESCRIPTION = "Read emails."

    def __init__(self, service, socketio):
        socket = BaseWebSocket("/app/calendar", socketio)
        listener = BaseCommandsListener()
        super().__init__(socket, listener)

