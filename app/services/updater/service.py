import json
import logging
from threading import RLock, Timer

from retask import Task

from app.core.messaging import Receiver, Sender
from app.core.service_base import BaseService, BackgroundProcessServiceStart


logger = logging.getLogger(__name__)


class UpdateScanner(object):
    UPDATE_CHECK_FREQ = 3600

    def __init__(self, queue_name):
        self.notification_sender = Sender(queue_name)
        self.timer = Timer(self.UPDATE_CHECK_FREQ, self.check_updates)

    def start(self):
        self.timer.start()

    def stop(self):
        pass


class UpdaterService(BackgroundProcessServiceStart, BaseService):
    def __init__(self, config):
        self.update_scanner = UpdateScanner("/shell/notifications")
        super().__init__()

    def get_component_name(self):
        return "updater"

    def on_service_start(self, *args, **kwargs):
        self.update_scanner.start()
        self.notify_start()

    def on_service_stop(self):
        self.update_scanner.stop()
