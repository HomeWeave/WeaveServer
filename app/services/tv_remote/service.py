import json
import logging
from threading import RLock

from roku import Roku

import app.core.netutils as netutils
from app.core.messaging import Receiver, Sender
from app.core.service_base import BaseService, BackgroundProcessServiceStart


logger = logging.getLogger(__name__)


class RokuScanner(object):
    def __init__(self, queue_name):
        self.sender = Sender(queue_name)
        self.sender.start()
        self.device_lock = RLock()
        self.device_map = {}

    def start_background_scan(self):
        devices = {}
        for roku in Roku.discover():
            mac = netutils.get_mac_address(roku.host)
            devices[mac] = RokuTV(mac, roku)
        with self.device_lock:
            self.device_map = devices

    def devices(self):
        with self.device_lock:
            return self.device_map.copy()


class TVRemoteReceiver(Receiver):
    def on_message(self, msg):
        logger.info("Got msg: %s", json.dumps(msg))


class TVRemoteService(BackgroundProcessServiceStart, BaseService):
    def __init__(self, config):
        self.receiver = TVRemoteReceiver("/tv/command")
        super().__init__()

    def get_component_name(self):
        return "tv_remote"

    def on_service_start(self, *args, **kwargs):
        self.receiver.start()
        self.notify_start()
        self.receiver.run()

    def on_service_stop(self):
        self.receiver.stop()
