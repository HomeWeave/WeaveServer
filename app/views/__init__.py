import sys

from .base import BaseView
from .simple_background_views import SimpleBackgroundView


class ViewManager(object):
    def __init__(self, nav_channel):
        self._view = BaseView()
        self.nav_channel = nav_channel

    @property
    def view(self):
        return self._view

    @view.setter
    def view(self, obj):
        self._view = obj
        #self.nav_channel.send_view(obj.html())

