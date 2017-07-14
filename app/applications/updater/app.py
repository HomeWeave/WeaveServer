"""
System Updates
"""

from functools import partial
import logging

from app.core.base_app import BaseApp, BaseCommandsListener
from app.core.base_app import BaseWebSocket
from app.system.updater import check_updates, run_ansible
from app.system.updater import do_reboot


logger = logging.getLogger(__name__)

class UpdaterApp(BaseApp):
    NAME = "System Updates"
    DESCRIPTION = "Check for System Updates."
    ICON = "fa-arrow-circle-o-up"


    def __init__(self, service, socketio):
        socket = BaseWebSocket("/app/updater", socketio)
        listener = BaseCommandsListener()
        super().__init__(socket, listener)

    def start(self):
        pass

    def start1(self):
        """
        Calls check_updates() and then repo.pull() on each of the repo instance
        while pushing the information out to the view.
        """
        logger.info("Starting UpdaterApp")

        def check_update_progress(val):
            self.flash_message("Checking ... {:.0%}".format(val))

        def check_pull_progress(base, val):
            self.flash_message(base + " ... {:.0%}".format(val))

        values = check_updates(check_update_progress)
        logger.info("Updates checked. Repos to update: " + str(values))
        for count, repo in enumerate(values):
            subtitle_params = count + 1, len(values), repo.repo_name
            subtitle = "({}/{}) Updating {}".format(*subtitle_params)

            self.flash_message(subtitle)
            repo.pull(partial(check_pull_progress, subtitle))

        if values:
            self.flash_message("Updating system configuration...")
            run_ansible()

            self.flash_message("Restarting...")
            do_reboot()
        else:
            self.flash_message("No updates found.")

    def flash_message(self, msg):
        self._view.view_args["subtitle"] = msg
        self._view.notify_updates()

