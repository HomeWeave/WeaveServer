from app.core.base_app import BaseApp, BaseCommandsListener
from app.core.base_app import BaseWebSocket

class CalendarApp(BaseApp):
    NAME = "Calendar"
    DESCRIPTION = "View Calendar events."
    ICON = "fa-calendar"

    def __init__(self, service, socketio):
        socket = BaseWebSocket("/app/calendar", socketio)
        listener = BaseCommandsListener()
        super().__init__(socket, listener)

