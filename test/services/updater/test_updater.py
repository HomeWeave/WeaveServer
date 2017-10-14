import os
import logging
from threading import Semaphore, Thread
from unittest.mock import patch, Mock

import git

from app.core.logger import configure_logging
from app.core.messaging import Receiver
from app.core.servicemanager import ServiceManager
from app.services.updater.service import UpdaterService, UpdateScanner


configure_logging()


def make_receiver(count, obj, sem, r):
    def on_message(msg):
        obj.update(msg)
        sem.release()
        nonlocal count
        count -= 1
        if not count:
            r.stop()
    return on_message


class TestUpdateScanner(object):
    def setup_method(self):
        self.git_repo = git.Repo
        UpdateScanner.list_repos = lambda x, y: ["dir"]
        UpdateScanner.get_repo = lambda x, y: Mock()
        self.update_check_freq_backup = UpdateScanner.UPDATE_CHECK_FREQ
        UpdateScanner.UPDATE_CHECK_FREQ = 5

        os.environ["USE_FAKE_REDIS"] = "TRUE"
        self.service_manager = ServiceManager(None)
        self.service_manager.start_services(["messaging"])

    def teardown_method(self):
        git.Repo = self.git_repo
        del os.environ["USE_FAKE_REDIS"]
        self.service_manager.stop()

    def test_update(self):
        self.service = UpdaterService(None)
        self.service.on_service_start()

        obj = {}
        sem = Semaphore(0)

        receiver = Receiver("/services/shell/notifications")
        receiver.on_message = make_receiver(1, obj, sem, receiver)
        receiver.start()
        Thread(target=receiver.run).start()

        assert not sem.acquire(timeout=2)
        repo.asssert_called_with("dir")

