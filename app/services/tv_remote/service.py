import json
import logging
from threading import RLock, Timer

from retask import Task
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
        with open("app/services/tv_remote/roku-commands.json") as inp:
            return json.load(inp)

    def device_id(self):
        return self.mac


class RokuScanner(object):
    def __init__(self, service_queue, scan_interval=600):
        self.service_sender = Sender(service_queue)
        self.service_sender.start()
        self.device_lock = RLock()
        self.device_map = {}
        self.scan_timer = Timer(scan_interval, self.scan)

    def start(self):
        self.scan()
        self.scan_timer.start()

    def stop(self):
        self.scan_timer.cancel()

    def scan(self):
        devices = {}
        for roku in self.discover_device():
            mac = self.get_device_id(roku.host)
            devices[mac] = RokuTV(mac, roku)
        with self.device_lock:
            self.device_map = devices

        for device_id, roku_tv in devices.items():
            obj = {
                "device_id": device_id,
                "device_command_queue": "/device/tv/command",
                "device_commands": roku_tv.list_commands(),
            }
            task = Task(obj)
            self.service_sender.enqueue(task, headers={"KEY": device_id})

    def discover_devices(self):
        return Roku.discover()

    def get_device_id(self, host):
        return netutils.get_mac_address(host)

    def get_device(self, device_id):
        with self.device_lock:
            return self.device_map[device_id]


class TVRemoteReceiver(Receiver):
    def __init__(self, scanner, queue_name):
        self.scanner = scanner
        super().__init__(queue_name)

    def on_message(self, msg):
        logger.info("Got msg: %s", json.dumps(msg))


class TVRemoteService(BackgroundProcessServiceStart, BaseService):
    def __init__(self, config):
        self.scanner = RokuScanner("/devices")
        self.receiver = TVRemoteReceiver(self.scanner, "/tv/command")
        super().__init__()

    def get_component_name(self):
        return "tv_remote"

    def on_service_start(self, *args, **kwargs):
        self.receiver.start()
        self.notify_start()
        self.receiver.run()
        self.scanner.start()

    def on_service_stop(self):
        self.scanner.stop()
        self.receiver.stop()
