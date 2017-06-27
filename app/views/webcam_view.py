from flask import render_template

from .base import BaseView


class WebcamView(BaseView):
    def __init__(self):
        super().__init__()

    def html(self):
        return self.render_template('webcam.html')

