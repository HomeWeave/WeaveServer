"""
Exposes a set of HTML based views that talk to view manager.
"""
import sys

from .base import BaseView
from .simple_background_views import SimpleBackgroundView
from .webcam_view import WebcamView


class ViewManager(object):
    def __init__(self, nav_channel):
        self._view = BaseView()
        self.nav_channel = nav_channel

    def get_view(self):
        return self._view

    def replace_view(self, obj):
        self._view = obj
        self.refresh_view()

    def refresh_view(self):
        self.nav_channel.update_view(self._view.html())

