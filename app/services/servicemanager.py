import threading

from .base import BlockingServiceStart


class ServiceManager(threading.Thread):
    def __init__(self, services, view_manager):
        self.services = services
        self.view_manager = view_manager
        self.cur_service = None
        super().__init__()

    def run(self):
        for service in self.services:
            self.cur_service = service()
            if isinstance(self.cur_service, BlockingServiceStart):
                self.view_manager.view = self.cur_service.view

            self.cur_service.service_start()




