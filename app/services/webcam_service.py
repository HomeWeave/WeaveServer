"""
A simple service that shows Webcam stream on the page.
"""
from app.views import WebcamView
from .base import BaseService, BlockingServiceStart


class WebcamService(BaseService, BlockingServiceStart):
    """ Shows the local webcam stream within a  <video> tag. """

    def __init__(self, observer=None):
        super().__init__(observer=observer)
        self._view = WebcamView()

    def on_service_start(self, *args, **kwargs):
        pass

    def view(self):
        return self._view

