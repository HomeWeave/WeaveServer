import logging
from threading import Event, Thread

from pywebostv.connection import WebOSClient
from pywebostv.controls import MediaControl

from app.core.netutils import get_mac_address
from app.core.rpc import ServerAPI, ArgParameter, RPCServer


logger = logging.getLogger(__name__)


def get_apis(client):
    media = MediaControl(client)

    return [
        ServerAPI("mute", "Mute the TV", [
            ArgParameter("state", "True to mute, False to unmute", bool)
        ], media.mute),
        ServerAPI("volume_up", "Increase Volume", [], media.volume_up),
        ServerAPI("volume_down", "Decrease Volume", [], media.volume_down),
    ]


class WebOSTV(object):
    def __init__(self, service, mac, client):
        self.mac = mac
        apis = get_apis(client)
        self.rpc = RPCServer("LG TV Commands", "Remote control for LG TVs.",
                             apis, service)

    def start(self):
        self.rpc.start()

    def stop(self):
        self.rpc.stop()


class WebOsScanner(object):
    SCAN_INTERVAL = 300

    def __init__(self, service):
        self.service = service
        self.shutdown = Event()
        self.scanner_thread = Thread(target=self.run)
        self.discovered_clients = {}
        self.store = {}

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
        new_clients = {}
        for client in WebOSClient.discover():
            logger.info("Found an LG Web OS TV at: %s", client.url)
            mac = get_mac_address(client.host)
            if mac not in self.discovered_clients:
                webos_tv = WebOSTV(self.service, mac, client)
                new_clients[mac] = webos_tv
                webos_tv.start()

        for key in set(self.discovered_clients.keys()) - set(new_clients):
            self.discovered_clients.pop(key)

        self.discovered_clients.update(new_clients)
