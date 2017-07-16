"""
System Updates
"""

from functools import partial
import logging

from app.core.base_app import BaseApp, BaseCommandsListener
from app.core.base_app import BaseWebSocket


logger = logging.getLogger(__name__)


class UpdaterWebSocket(BaseWebSocket):
    def __init__(self, app, socketio):
        self.app = app
        self.socketio = socketio

    def notify_status(self, status):
        self.reply_all('status', {"status": status})

    def notify_title(self, title):
        self.reply_all('title', {"title": title})

class UpdaterApp(BaseApp):
    NAME = "System Updates"
    DESCRIPTION = "Check for System Updates."
    ICON = "fa-arrow-circle-o-up"


    def __init__(self, service, socketio):
        self.socket = UpdaterWebSocket("/app/updater", socketio)
        super().__init__(self.socket, BaseCommandsListener())

        self.check_updates = service.api(self, "check_updates")

    def start(self):
        """
        Calls check_updates() and then repo.pull() on each of the repo instance
        while pushing the information out to the view.
        """
        logger.info("Starting UpdaterApp")

        def check_update_progress(val):
            self.flash_message("Checking ... {:.0%}".format(val))

        def check_pull_progress(base, val):
            self.flash_message(base + " ... {:.0%}".format(val))

        values = self.check_updates(check_update_progress)
        logger.info("Updates checked. Repos to update: " + str(values))
        for count, repo in enumerate(values):
            subtitle_params = count + 1, len(values), repo.repo_name
            subtitle = "({}/{}) Updating {}".format(*subtitle_params)

            self.flash_title("Updating")
            self.flash_message(subtitle)
            repo.pull(partial(check_pull_progress, subtitle))

        if values:
            self.flash_message("Updating system configuration...")
            run_ansible()

            self.flash_title("Done!")
            self.flash_message("Updates will be applied when you restart the system")
        else:
            self.flash_message("")
            self.flash_title("No Updates Found")

    def flash_message(self, msg):
        self.socket.notify_status(msg)

    def flash_title(self, msg):
        self.socket.notify_title(msg)
