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
        self._view.args["subtitle"] = "Please wait ..."

    def on_service_start(self):
        def check_update_progress(val):
            self._view.args["subtitle"] = "Checking ... {:.0%}".format(val)
            self.observer()

        def check_pull_progress(base, val):
            self._view.args["subtitle"] = base + " ... {:.0%}".format(val)
            self.observer()

        values = check_updates(check_update_progress)
        for count, repo in enumerate(values):
            subtitle_params = count + 1, len(values), repo.repo_name
            subtitle = "({}/{}) Updating {}".format(*subtitle_params)

            self._view.args["subtitle"] = subtitle
            self.observer()
            repo.pull(partial(check_pull_progress, subtitle))

        if len(values):
            self._view.args["subtitle"] = "Updating system configuration..."
            self.observer()
            run_ansible()

            self._view.args["subtitle"] = "Restarting..."
            self.observer()
            do_reboot()

    def view(self):
        return self._view

