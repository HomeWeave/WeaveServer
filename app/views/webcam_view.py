"""
Contains WebcamView.
"""
from .base import BaseView


class WebcamView(BaseView):
    """A simple view that show a <video> element that streams Webcam video."""

    def html(self):
        return self.render_template('webcam.html')

