from app.views import SimpleHeaderView
from app.applications.base import BaseApplication

class GmailApp(BaseApplication):
    ICON = "fa-envelope"
    NAME = "Gmail"
    DESCRIPTION = "Read emails."

    NAMESPACE = "/app/GMailApp"

    def __init__(self, service, socketio):
        view = SimpleHeaderView(self.NAMESPACE, socketio, "Gmail")
        super().__init__(service, socketio, view)

