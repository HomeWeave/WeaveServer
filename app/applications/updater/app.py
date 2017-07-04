"""
System Updates
"""

from functools import partial
import logging

from app.applications.base import BaseApplication
from app.system.updater import check_updates, run_ansible
from app.system.updater import do_reboot
from app.views import SimpleHeaderView


logger = logging.getLogger(__name__)

class UpdaterApp(BaseApplication):
    NAME = "System Updates"
    DESCRIPTION = "Check for System Updates."
    ICON = "fa-arrow-circle-o-up"


    NAMESPACE = "/app/UpdaterApp"

    def __init__(self, service, socketio):
        view = SimpleHeaderView(self.NAMESPACE, socketio, "Checking for updates")
        super().__init__(service, socketio, view)


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

    def flash_message(self, msg):
        self._view.view_args["subtitle"] = msg
        self._view.notify_updates()

