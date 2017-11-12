import json
import logging
from threading import RLock, Thread, Event

from roku import Roku
from wakeonlan import wol

import app.core.netutils as netutils
from app.core.services import BaseService, BackgroundProcessServiceStart
from app.core.services import EventDrivenService


logger = logging.getLogger(__name__)


class RokuTV(object):
    def __init__(self, mac, roku):
        super().__init__()
        self.mac = mac
        self.roku = roku
        self.commands = self.read_commands()
        self.command_ids = [x["id"] for x in self.commands]

    def on_command(self, command_id, command_args):
        try:
            func = getattr(self, "handle_" + command_id)
        except AttributeError:
            try:
                func = getattr(self.roku, command_id)
            except AttributeError:
                return False
        func(*command_args)
        return True

    def read_commands(self):
        with open("app/services/tv_remote/roku-commands.json") as inp:
            return json.load(inp)

    def handle_power(self):
        if netutils.ping_host(self.roku.host):
            self.roku._post("/keypress/Power")
        else:
            # TV is probably unreachable because its off. Send a WOL packet.
            wol.send_magic_packet(self.mac)

    def register(self, service):
        def make_cmd(item):
            return {
                "enum": [item["id"]],
                "title": item["name"],
                "input_type": item["type"]
            }
        params = {
            "command_id": {
                "anyOf": [make_cmd(x) for x in self.read_commands()]
            },
            "command_args": {"type": "string"}
        }
        service.express_capability("Roku Remote", "TV Remote for Roku", params,
                                   self.on_command)


class RokuScanner(object):
    SCAN_INTERVAL = 60

    def __init__(self, service):
        self.service = service
        self.device_lock = RLock()
        self.shutdown = Event()
        self.scanner_thread = Thread(target=self.run)

    def start(self):
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
        for roku in self.discover_devices():
            logger.info("Found a Roku TV at %s", roku.host)
            mac = self.get_device_id(roku.host)
            tv = RokuTV(mac, roku)
            tv.register(self.service)

    def discover_devices(self):
        for _ in range(3):
            obj = Roku.discover()
            if obj:
                return obj
        return []

    def get_device_id(self, host):
        return netutils.get_mac_address(host)


class TVRemoteService(EventDrivenService, BackgroundProcessServiceStart,
                      BaseService):
    def __init__(self, config):
        self.scanner = RokuScanner(self)
        super().__init__()

    def get_component_name(self):
        return "tv_remote"

    def on_service_start(self, *args, **kwargs):
        super().on_service_start()
        self.notify_start()
        self.scanner.start()

    def on_service_stop(self):
        self.scanner.stop()
        super().on_service_stop()
