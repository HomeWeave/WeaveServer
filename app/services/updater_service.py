from app.system.updater import check_updates, do_upgrade
from app.views import SimpleBackgroundView
from .base import BaseService, BlockingServiceStart


class UpdaterService(BaseService, BlockingServiceStart):
    def __init__(self):
        super().__init__()
        self._view = SimpleBackgroundView("Checking for updates.")

    def on_service_start(self):
        values = check_updates()
        for val in values:
            self._view.args["subtitle"] = val
            do_upgrade([val])

    @property
    def view(self):
        return self._view
