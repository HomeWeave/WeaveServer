from app.core.base_app import BaseApp, BaseCommandsListener
from app.core.base_app import BaseWebSocket


class WebcamApp(BaseApp):
    ICON = "fa-camera"
    NAME = "Webcam"
    DESCRIPTION = "Click photos from webcam."

    def __init__(self, service, socketio):
        socket = BaseWebSocket("/app/webcam", socketio)
        listener = BaseCommandsListener()
        super().__init__(socket, listener)


