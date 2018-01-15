import json
import logging
import socket
import time
from base64 import b64encode
from ipaddress import IPv4Network
from ipaddress import IPv4Address
from threading import Event, Thread, RLock

import cv2
import requests

import app.core.netutils as netutils
from app.core.messaging import Sender, Creator, QueueAlreadyExists
from app.core.rpc import RPCServer, ArgParameter, ServerAPI
from app.core.services import BaseService, BackgroundProcessServiceStart
from app.core.services.http import AppHTTPServer


logger = logging.getLogger(__name__)


class DahuaStream(object):
    FRAME_TIME_SPACING = 1.0  # Next frame is atleast 1.0 seconds after last.

    def __init__(self, url, on_grab):
        self.url = url
        self.on_grab = on_grab
        self.capture = None
        self.stopped = Event()
        self.capture_thread = None

    def start(self):
        logger.info("starting url: %s", self.url)
        self.capture = cv2.VideoCapture(self.url)
        self.stopped.clear()
        self.capture_thread = Thread(target=self.run)
        self.capture_thread.start()

    def stop(self):
        self.stopped.set()
        self.capture_thread.join()
        self.capture = None

    def run(self):
        last_capture = 0
        while not self.stopped.wait(0.5):
            ret, frame = self.capture.read()
            if not ret:
                logger.error("Unable to read Dahua Stream at %s", self.url)
                break

            cur_time = time.time()
            if cur_time - last_capture > self.FRAME_TIME_SPACING:
                self.on_grab(self.encode(frame))
                last_capture = cur_time

        self.capture.release()

    def encode(self, frame):
        binary = cv2.imencode('.png', frame)[1]
        return str(b64encode(binary), 'ascii')


class DahuaMessagingBridge(object):
    def __init__(self, service, host, username, pwd, cam):
        self.host = host
        self.cam = cam
        url = "rtsp://{}:{}@{}:554/cam/realmonitor".format(username, pwd, host)
        url = url + "?channel={}&subtype=0".format(cam)

        self.queue = service.get_service_queue_name("stream/dahua" + str(cam))
        self.sender = Sender(self.queue)
        self.stream = DahuaStream(url, self.send_frame)
        self.running = False

    def start(self):
        creator = Creator()
        creator.start()
        try:
            creator.create({
                "queue_name": self.queue,
                "queue_type": "sticky",
                "request_schema": {"type": "string"}
            })
        except QueueAlreadyExists:
            pass

        self.sender.start()
        self.running = True

    def stop(self):
        if not self.running:
            return

        self.running = False
        if self.stream.capture is not None:
            self.stream.stop()
        self.sender.close()

    def send_frame(self, obj):
        self.sender.send(obj)

    def fingerprint(self):
        mac = netutils.get_mac_address(self.host).replace(":", "-")
        return "rtsp-{}-cam-{}".format(mac, self.cam)

    @property
    def info_message(self):
        return {
            "id": self.fingerprint(),
            "queue": self.queue,
            "active": self.stream.capture is not None
        }

    @staticmethod
    def discover(service, username, pwd):
        logger.info("Scanning for Dahua Cameras.")
        res = []
        for ip_obj in netutils.iter_ipv4_addresses():
            net = IPv4Network(ip_obj["addr"] + "/" + ip_obj["netmask"],
                              strict=False)
            if net.is_loopback:
                continue

            for ip in net.hosts():
                if ip <= IPv4Address("192.168.1.115"):
                    continue
                if ip > IPv4Address("192.168.1.120"):
                    continue

                if DahuaMessagingBridge.check_ip(ip):
                    res.append(str(ip))

        logger.info("Found %d Dahua Cameras.", len(res))

        return [DahuaMessagingBridge(service, str(x), username, pwd, y)
                for x in res for y in range(1, 5)]

    @staticmethod
    def check_ip(host):
        if not DahuaMessagingBridge.checK_socket(host, 554):
            return False

        return "WEB SERVICE" in requests.get("http://{}/".format(host)).text

    @staticmethod
    def checK_socket(ip, port):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.2)
        try:
            sock.connect((str(ip), port))
            return True
        except IOError:
            return False
        finally:
            sock.close()


class VideoStreamManager(object):
    SERVER_PORT = 23034
    ACTIVE_POLL_TIME = 60

    def __init__(self, service, config):
        self.service = service
        self.config = config
        self.exited = Event()
        self.stopped = Event()

        self.cur_bridges = {}
        self.cur_bridges_lock = RLock()

    def run(self, success_callback=None):
        success_callback()

        config = self.config
        searches = [
            lambda: DahuaMessagingBridge.discover(
                self.service, config["dahua"]["DAHUA_USERNAME"],
                config["dahua"]["DAHUA_PWD"]),
        ]

        while True:
            new_bridges = {}
            for search in searches:
                bridges = {x.fingerprint(): x for x in search()}
                new_bridges.update(bridges)

            new_ids = set(bridges.keys())

            with self.cur_bridges_lock:
                old_ids = set(self.cur_bridges.keys())

                to_stop = []
                for dead in old_ids - new_ids:
                    to_stop.append(self.cur_bridges.pop(dead))

                to_start = []
                for new in new_ids - old_ids:
                    self.cur_bridges[new] = new_bridges[new]
                    to_start.append(new_bridges[new])

            logger.info("Found %d new cameras", len(to_start))
            for new_bridge in to_start:
                new_bridge.start()

            for old_bridge in to_stop:
                old_bridge.stop()

            if self.exited.wait(timeout=self.ACTIVE_POLL_TIME):
                break

        with self.cur_bridges_lock:
            for bridge in self.cur_bridges.values():
                bridge.stop()
            self.cur_bridges = {}

        self.stopped.set()

    def stop(self):
        self.exited.set()
        self.stopped.wait()

    def start_stream(self, cam_id):
        bridge = self.cur_bridges.get(cam_id)
        if bridge is None:
            return

        logger.info("Starting stream: %s", cam_id)
        bridge.stream.start()

    def stop_stream(self, cam_id):
        bridge = self.cur_bridges.get(cam_id)
        if bridge is None:
            return

        logger.info("Stopping stream: %s", cam_id)
        bridge.stream.stop()

    def list_streams(self):
        with self.cur_bridges_lock:
            obj = {x: y.info_message for x, y in self.cur_bridges.items()}
            logger.info("Listing respomse: " + str(obj))
            return obj

    @property
    def info_message(self):
        return {k: v.info_message for k, v in self.cur_bridges.items()}


class CameraService(BackgroundProcessServiceStart, BaseService):
    def __init__(self, config):
        self.server = VideoStreamManager(self, config)
        self.rpc = RPCServer("Camera", "Manage Cameras/CCTV", [
            ServerAPI("start_stream", "Starts the stream of given camera", [
                ArgParameter("camera_id", "ID of the camera", str)
            ], self.server.start_stream),
            ServerAPI("stop_stream", "Stops the stream of given camera", [
                ArgParameter("camera_id", "ID of the camera", str)
            ], self.server.stop_stream),
            ServerAPI("list_streams", "Lists all available streams.", [],
                      self.server.list_streams)
        ], self)
        self.http = AppHTTPServer(self, fa_favicon="video-camera")
        super().__init__()

    def handle_cameras_request(self):
        return json.dumps(self.server.info_message)

    def get_component_name(self):
        return "camera"

    def on_service_start(self, *args, **kwargs):
        self.http.start()
        self.rpc.start()
        self.server.run(self.notify_start)

    def on_service_stop(self):
        self.server.stop()
