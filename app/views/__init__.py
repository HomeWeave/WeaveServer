import sys

from .base import BaseView
from .simple_background_views import SimpleBackgroundView


class ViewManager(object):
    def __init__(self):
        self._view = BaseView()
        self.can_change = False

    @property
    def view(self):
        return self._view

    @view.setter
    def view(self, obj):
        self._view = obj


view_manager = ViewManager()
