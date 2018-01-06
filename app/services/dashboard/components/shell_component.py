import logging
from threading import Thread, RLock

from app.core.messaging import Receiver, Sender

from .base import BaseComponent

logger = logging.getLogger(__name__)


class AppLister(object):
    def __init__(self, shell_component):
        self.apps = []
        self.shell_component = shell_component
        self.app_list_receiver = Receiver("/_system/applications")

    def start(self):
        self.app_list_receiver.on_message = self.process_app_list_message
        self.app_list_receiver.start()

        self.receiver_thread = Thread(target=self.app_list_receiver.run)
        self.receiver_thread.start()

    def stop(self):
        self.app_list_receiver.stop()
        self.receiver_thread.join()

    def process_app_list_message(self, msg):
        self.apps = msg
        for obj in self.apps.values():
            obj["kind"] = "APP"

        self.shell_component.notify_all('dock_apps', self.apps)


class ShellComponent(BaseComponent):
    def __init__(self, ws_manager):
        super(ShellComponent, self).__init__("/shell")
        self.ws_manager = ws_manager
        self.app_lister = AppLister(self)
        self.senders = {}
        self.senders_lock = RLock()

    def activate(self):
        self.app_lister.start()

    def deactivate(self):
        self.app_lister.stop()

    def on_list_apps(self, msg):
        self.reply('dock_apps', self.app_lister.apps)

    def on_messaging(self, obj):
        queue = obj["queue"]
        data = obj["data"]
        # self.get_sender(uri).send(data)
        sender = Sender(queue)
        sender.start()
        logger.info("Sent Message to %s: %s", queue, str(data))
        sender.send(data)

    def get_sender(self, queue):
        with self.senders_lock:
            if queue in self.senders:
                return self.senders[queue]
            sender = Sender(queue)
            self.senders[queue] = sender
        sender.start()
        return sender
