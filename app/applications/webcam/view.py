import os.path

from app.views import BaseView, BaseViewWebSocket


class WebcamViewWebSocket(BaseViewWebSocket):
    pass

class WebcamView(BaseView):

    HTML = "webcam.html"
    HTML_BASE_PATH = os.path.dirname(os.path.realpath(__file__))

    def __init__(self, namespace, socketio, app):
        main_sock = WebcamViewWebSocket(self, namespace, socketio)
        super().__init__(main_sock)
        self.view_args["click_button"] = {"enabled": True, "text": "Click!"}
