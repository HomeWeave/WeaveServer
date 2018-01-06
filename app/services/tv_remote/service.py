from threading import Event

from app.core.services import BaseService, BackgroundProcessServiceStart
from app.core.services import EventDrivenService

from .roku import RokuScanner
from .webos import WebOsScanner


class TVRemoteService(EventDrivenService, BackgroundProcessServiceStart,
                      BaseService):
    def __init__(self, config):
        self.roku_scanner = RokuScanner(self)
        self.webos_scanner = WebOsScanner(self)
        self.shutdown = Event()
        super().__init__()

    def get_component_name(self):
        return "tv_remote"

    def on_service_start(self, *args, **kwargs):
        super().on_service_start()
        self.notify_start()
        self.roku_scanner.start()
        self.webos_scanner.start()
        self.shutdown.wait()

    def on_service_stop(self):
        self.shutdown.set()

        self.roku_scanner.stop()
        self.webos_scanner.stop()
        super().on_service_stop()
