from app.views import SimpleHeaderView
from app.applications.base import BaseApplication

class WebcamApp(BaseApplication):
    ICON = "fa-camera"
    NAME = "Webcam"
    DESCRIPTION = "Click photos from webcam."

    NAMESPACE = "/app/WebcamApp"

    def __init__(self, service, socketio):
        view = SimpleHeaderView(self.NAMESPACE, socketio, "Webcam")
        super().__init__(service, socketio, view)

