from app.views import SimpleHeaderView
from app.applications.base import BaseApplication

class CalendarApp(BaseApplication):
    NAME = "Calendar"
    DESCRIPTION = "View Calendar events."
    ICON = "fa-calendar"

    NAMESPACE = "/app/CalendarApp"

    def __init__(self, service, socketio):
        view = SimpleHeaderView(self.NAMESPACE, socketio, "Calendar")
        super().__init__(service, socketio, view)

