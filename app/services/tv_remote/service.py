import json
import logging
from threading import RLock, Thread, Event

from retask import Task
from roku import Roku
from wakeonlan import wol

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

        try:
            func = getattr(self, "handle_" + command["id"])
        except AttributeError:
            try:
                func = getattr(self.roku, command["id"])
            except AttributeError:
                return False
        func(*command["params"])
        return True

    def read_commands(self):
        with open("app/services/tv_remote/roku-commands.json") as inp:
            return json.load(inp)

    def device_id(self):
        return self.mac

    def handle_power(self):
        if netutils.ping_host(self.roku.host):
            self.roku._post("/keypress/Power")
        else:
            # TV is probably unreachable because its off. Send a WOL packet.
            wol.send_magic_packet(self.mac)


class RokuScanner(object):
    SCAN_INTERVAL = 60

    def __init__(self, service_queue):
        self.service_sender = Sender(service_queue)
        self.device_lock = RLock()
        self.device_map = {}
        self.shutdown = Event()
        self.scanner_thread = Thread(target=self.run)

    def start(self):
        self.service_sender.start()
        self.scan()
        self.scanner_thread.start()

    def stop(self):
        self.shutdown.set()
        self.scanner_thread.join()

    def run(self):
        while not self.shutdown.is_set():
            self.scan()
            self.shutdown.wait(timeout=self.SCAN_INTERVAL)

    def scan(self):
        devices = {}
        for roku in self.discover_devices():
            logger.info("Found a Roku TV at %s", roku.host)
            mac = self.get_device_id(roku.host)
            devices[mac] = RokuTV(mac, roku)
        with self.device_lock:
            self.device_map = devices

        for device_id, roku_tv in devices.items():
            obj = {
                "device_id": device_id,
                "device_commands_queue": "/device/tv/command",
                "device_commands": roku_tv.list_commands(),
            }
            task = Task(obj)
            self.service_sender.send(task, headers={"KEY": device_id})

    def discover_devices(self):
        for _ in range(3):
            obj = Roku.discover()
            if obj:
                return obj
        return []

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
        try:
            device = self.scanner.get_device(msg["device_id"])
        except KeyError:
            logger.warning("Not found device id: %s.", msg["device_id"])
            return

        command = {
            "id": msg["command_id"],
            "params": msg.get("args", [])
        }

        if device.send_command(command):
            logger.info("Command %s sent to %s", command, device)
        else:
            logger.info("Could not send command %s to %s", command, device)


class TVRemoteService(BackgroundProcessServiceStart, BaseService):
    def __init__(self, config):
        self.scanner = RokuScanner("/devices")
        self.receiver = TVRemoteReceiver(self.scanner, "/device/tv/command")
        super().__init__()

    def get_component_name(self):
        return "tv_remote"

    def on_service_start(self, *args, **kwargs):
        self.receiver.start()
        self.notify_start()
        self.scanner.start()
        self.receiver.run()

    def on_service_stop(self):
        self.scanner.stop()
        self.receiver.stop()
