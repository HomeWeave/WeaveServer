"""
Contains UpdaterService that shows a UI while updating components in the background.
"""

from functools import partial
import logging

from app.system.updater import check_updates, run_ansible
from app.system.updater import do_reboot
from app.views import SimpleHeaderView
from .base import BaseService, BlockingServiceStart


logger = logging.getLogger(__name__)

class UpdaterService(BaseService, BlockingServiceStart):
    """
    Uses a SimpleHeaderView to show "Checking for updates". Realtime update
    information is shown in the view using the subtitle arg.
    """

    NAMESPACE = "/updater"

    def __init__(self, socketio):
        msg = "Checking for updates."
        view = SimpleHeaderView(self.NAMESPACE, socketio, msg)
        super().__init__(view=view)
        self.flash_message("Please wait ...")

    def on_service_start(self, *args, **kwargs):
        """
        Calls check_updates() and then repo.pull() on each of the repo instance
        while pushing the information out to the view.
        """
        logger.info("Starting Updater Service.")

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
        self._view.args["subtitle"] = msg
        self._view.notify_updates()

