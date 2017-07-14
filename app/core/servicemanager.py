"""
Contains components that manage services, their sequences and interdependence (later)
"""

import threading
import logging


logger = logging.getLogger(__name__)


class ServiceManager(threading.Thread):
    """
    Sequentially starts services using service.service_start(). When a new
    service is activated, view_manager is updated with its view.
    """
    def __init__(self, services, socket_manager):
        self.services = services
        self.cur_service = None
        self.socket_manager = socket_manager
        super().__init__()

    def run(self):
        """ Sequentially starts all the services."""
        logger.info("Starting services...")
        for service_cls in self.services:
            self.cur_service = service_cls(self.socket_manager)
            self.cur_service.service_start()

