from app.views import WebcamView
from .base import BaseService, BlockingServiceStart


class WebcamService(BaseService, BlockingServiceStart):
    def __init__(self, observer=None):
        super().__init__(observer=observer)
        self._view = WebcamView()

    def on_service_start(self):
        pass

    def view(self):
        return self._view

