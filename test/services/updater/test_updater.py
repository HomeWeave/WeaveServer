import os
import logging
from threading import Semaphore, Thread
from unittest.mock import patch, Mock

import git

from app.core.logger import configure_logging
from app.core.messaging import Receiver, Sender
from app.core.services import ServiceManager
from app.services.updater.service import UpdaterService, UpdateScanner
from app.services.updater.service import Updater


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
        self.update_check_freq_backup = UpdateScanner.UPDATE_CHECK_FREQ
        UpdateScanner.UPDATE_CHECK_FREQ = 5

        os.environ["USE_FAKE_REDIS"] = "TRUE"
        self.service_manager = ServiceManager(None)
        self.service_manager.start_services(["messaging"])

    def teardown_method(self):
        del os.environ["USE_FAKE_REDIS"]
        logging.info("Stopping service manager..")
        self.service_manager.stop()

    def tst_simple_update(self):
        mock_repo = Mock()
        mock_repo.needs_pull = Mock(return_value=False)
        UpdateScanner.list_repos = lambda x, y: ["dir"]
        UpdateScanner.get_repo = lambda x, y: mock_repo

        service = UpdaterService(None)
        Thread(target=service.on_service_start).start()

        obj1 = {}
        sem1 = Semaphore(0)

        r1 = Receiver("/services/shell/notifications")
        r1.on_message = make_receiver(2, obj1, sem1, r1)
        r1.start()
        Thread(target=r1.run).start()

        assert sem1.acquire(timeout=2)
        assert obj1 == {}

        assert not sem1.acquire(timeout=2)
        mock_repo.asssert_called_with("dir")

        mock_repo.needs_pull = Mock(return_value=True)
        assert sem1.acquire(timeout=5)
        assert next(x for x in obj1.values()) == {"message": "Update available."}
        service.on_service_stop()

    def tst_trigger_update_when_no_update(self):
        mock_repo = Mock()
        mock_repo.needs_pull = Mock(return_value=False)
        UpdateScanner.list_repos = lambda x, y: ["dir"]
        UpdateScanner.get_repo = lambda x, y: mock_repo
        Updater.perform_ansible_update = lambda x: True

        scanner = UpdateScanner(UpdaterService.NOTIFICATION_QUEUE,
                                UpdaterService.UPDATER_STATUS_QUEUE)
        scanner.notification_sender.start()
        scanner.status_sender.start()

        updater = Updater(scanner, UpdaterService.UPDATER_COMMAND_QUEUE,
                          UpdaterService.UPDATER_STATUS_QUEUE)
        updater.start()
        scanner.check_updates()

        r1 = Receiver("/services/updater/status")
        r1.start()
        assert r1.receive().task == {"message": "No updates available."}

        sender = Sender("/services/updater/command")
        sender.start()
        sender.send({"action": "TRIGGER"})

        assert r1.receive().task == {"message": "No updates available."}

        scanner.status_sender.close()
        scanner.notification_sender.close()
