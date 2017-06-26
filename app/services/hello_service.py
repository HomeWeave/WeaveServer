import time

from app.views import SimpleBackgroundView
from .base import BaseService, BlockingServiceStart


class HelloService(BaseService, BlockingServiceStart):
    def __init__(self, observer=None):
        super().__init__(observer=observer)
        self._view = SimpleBackgroundView("Hello!")

    def on_service_start(self):
        time.sleep(30)

    def view(self):
        return self._view

