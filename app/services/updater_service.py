from os.path import basename
from functools import partial

from app.system.updater import check_updates, run_ansible
from app.system.updater import do_reboot
from app.views import SimpleBackgroundView
from .base import BaseService, BlockingServiceStart


class UpdaterService(BaseService, BlockingServiceStart):
    def __init__(self, observer=None):
        super().__init__(observer=observer)
        self._view = SimpleBackgroundView("Checking for updates.")
        self.flash_message("Please wait ...")

    def on_service_start(self):
        def check_update_progress(val):
            self.flash_message("Checking ... {:.0%}".format(val))

        def check_pull_progress(base, val):
            self.flash_message(base + " ... {:.0%}".format(val))

        values = check_updates(check_update_progress)
        for count, repo in enumerate(values):
            subtitle_params = count + 1, len(values), repo.repo_name
            subtitle = "({}/{}) Updating {}".format(*subtitle_params)

            self.flash_message(subtitle)
            repo.pull(partial(check_pull_progress, subtitle))

        if len(values):
            self.flash_message("Updating system configuration...")
            run_ansible()

            self.flash_message("Restarting...")
            do_reboot()

    def flash_message(self, msg):
        self._view.args["subtitle"] = msg
        self.observer()

    def view(self):
        return self._view

