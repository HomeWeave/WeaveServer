import os
from unittest.mock import patch

from app.core.messaging import Receiver
from app.core.servicemanager import ServiceManager
from app.services.updater.service import UpdaterService, UpdateScanner


@patch("git.Repo")
class TestUpdateScanner(object):
    def setup_method(self):
        self.update_check_freq_backup = UpdateScanner.UPDATE_CHECK_FREQ
        UpdateScanner.UPDATE_CHECK_FREQ = 1

        os.environ["USE_FAKE_REDIS"] = "TRUE"
        self.service_manager = ServiceManager(None)
        self.service_manager.start_services(["messaging"])

    def teardown_method(self):
        del os.environ["USE_FAKE_REDIS"]
        self.service_manager.stop()

    def test_no_update(self):
        self.service = UpdaterService(None)
        self.service.on_service_start()

        receiver = Receiver("/shell/notifications")
        receiver.start()
        msg = receiver.receive().task.data

