import logging
from threading import Thread

from app.core.messaging import Receiver

from .base import BaseComponent


logger = logging.getLogger(__name__)


class DockComponent(BaseComponent):
    def __init__(self, shell_component):
        super(DockComponent, self).__init__("/dock")
        self.apps = []
        self.shell_component = shell_component

    def activate(self):
        self.rpc_list_receiver = Receiver("/_system/rpc-servers")
        self.rpc_list_receiver.on_message = self.process_rpc_list_message
        self.rpc_list_receiver.start()

        self.receiver_thread = Thread(target=self.rpc_list_receiver.run)
        self.receiver_thread.start()

    def deactivate(self):
        self.rpc_list_receiver.stop()
        self.receiver_thread.join()

    def process_rpc_list_message(self, msg):
        self.apps = msg
        self.notify_all('dock_apps', msg)

    def on_list(self, msg):
        self.reply('dock_apps', self.apps)

    def on_launch(self, msg):
        print(msg)
