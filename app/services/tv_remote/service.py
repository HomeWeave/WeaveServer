import json
import logging
from threading import RLock

from roku import Roku

import app.core.netutils as netutils
from app.core.messaging import Receiver, Sender
from app.core.service_base import BaseService, BackgroundProcessServiceStart


logger = logging.getLogger(__name__)

class TV(object):
    def list_commands(self):
        return []

    def send_command(self, command_id):
        pass

    def powered(self):
        return False

    def device_id(self):
        return None


class RokuTV(TV):
    def __init__(self, mac, roku):
        super().__init__()
        self.mac = mac
        self.roku = roku
        self.commands = self.read_commands()
        self.command_ids = [x["id"] for x in self.commands]

    def list_commands(self):
        return self.commands

    def send_command(self, command):
        if command["id"] not in self.command_ids:
            logger.warning("%s not in commands.", command["id"])
            return False

        func = getattr(self.roku, command["id"])
        func(*command["params"])
        return True

    def read_commands(self):
        with open("roku-commands.json") as inp:
            return json.load(inp)

    def device_id(self):
        return self.mac


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
