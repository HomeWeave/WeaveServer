"""
A dummy service that says "Hello"
"""

import time

from app.views import SimpleBackgroundView
from .base import BaseService, BlockingServiceStart


class HelloService(BaseService, BlockingServiceStart):
    """ Shows "Hello!" within an <h1> and sleeps for 10 seconds. """

    def __init__(self, observer=None):
        super().__init__(observer=observer)
        self._view = SimpleBackgroundView("Hello!")

    def on_service_start(self, *args, **kwargs):
        time.sleep(10)

    def view(self):
        return self._view

