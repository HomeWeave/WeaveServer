"""
Contains components that manage services, their sequences and interdependence (later)
"""

import threading

from .base import BlockingServiceStart


class ServiceManager(threading.Thread):
    """
    Sequentially starts services using service.service_start(). When a new
    service is activated, view_manager is updated with its view.
    """
    def __init__(self, services, view_manager):
        self.services = services
        self.view_manager = view_manager
        self.cur_service = None
        super().__init__()

    def run(self):
        """ Sequentially starts all the services."""
        for service in self.services:
            self.cur_service = service(observer=self.notify_view_updates)
            if isinstance(self.cur_service, BlockingServiceStart):
                self.view_manager.replace_view(self.cur_service.view())

            self.cur_service.service_start()

    def notify_view_updates(self):
        self.view_manager.refresh_view()

