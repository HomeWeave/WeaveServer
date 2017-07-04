from app.views import BaseView, BaseViewWebSocket
from app.applications.base import BaseApplication
from .view import WebcamView


class WebcamApp(BaseApplication):
    ICON = "fa-camera"
    NAME = "Webcam"
    DESCRIPTION = "Click photos from webcam."

    NAMESPACE = "/app/WebcamApp"

    def __init__(self, service, socketio):
        view = WebcamView(self.NAMESPACE, socketio, self)
        super().__init__(service, socketio, view)


