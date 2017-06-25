import time

from app.views import SimpleBackgroundView
from .base import BaseService, BlockingServiceStart


class HelloService(BaseService, BlockingServiceStart):
    def __init__(self):
        super().__init__()
        self._view = SimpleBackgroundView("Hello!")

    def on_service_start(self):
        time.sleep(30)

    @property
    def view(self):
        return self._view

