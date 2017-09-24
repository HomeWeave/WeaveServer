import json
import logging

from app.core.messaging import Receiver
from app.core.service_base import BaseService, BackgroundProcessServiceStart


logger = logging.getLogger(__name__)


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
        def on_start():
            self.notify_start()
        self.receiver.run(on_start)

    def on_service_stop(self):
        self.receiver.stop()
