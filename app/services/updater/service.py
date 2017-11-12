import logging
import os
import subprocess
from threading import Thread, Event

from git import Repo
from git.util import RemoteProgress
from git.exc import GitError

from app.core.messaging import Receiver, Sender
from app.core.services import BaseService, BackgroundProcessServiceStart
from app.core.services import EventDrivenService, StatusService


logger = logging.getLogger(__name__)
SCRIPTS_DIR = "/home/rpi/scripts"
CODE_DIR = os.path.expanduser("~/Code")


class PercentProgressIndicator(RemoteProgress):
    """Specialization that calls back a function with a percentage indicator"""
    def __init__(self, callback):
        self.callback = callback
        super().__init__()

    def update(self, op_code, cur_count, max_count=None, message=""):
        if max_count is not None:
            self.callback(0)
        else:
            self.callback(cur_count / float(max_count))


class Repository(object):
    """Encapsulates a Git Repository"""
    def __init__(self, path):
        """
        :param path: Path to the git repo.
        """
        self.path = path
        self.repo_name = os.path.basename(path)
        self.repo = Repo(self.path)

    def clean_untracked(self):
        """ Does git clean -dfx """
        self.repo.git.clean("-dfx")

    def reset_hard(self):
        """" Does git reset --hard """
        self.repo.git.reset('--hard')

    def needs_pull(self):
        """Does git fetch, and checks whether local tip of master is same as
        that of upstream master."""
        for remote in self.repo.remotes:
            logger.info("Pulling remote for repo: %s", self.repo_name)
            remote.fetch()

        for _ in self.repo.iter_commits('master..origin/master'):
            logger.info("Repo %s needs update", self.repo_name)
            return True
        return False

    def pull(self, progress_observer=None):
        """ Pulls from master. """
        logger.info("Updating repo: %s", self.repo_name)
        self.clean_untracked()
        self.reset_hard()
        origin = self.repo.remotes.origin
        origin.pull(progress=PercentProgressIndicator(progress_observer))


class UpdateScanner(object):
    UPDATE_CHECK_FREQ = 3600

    def __init__(self, service):
        self.service = service
        self.cancel_event = Event()
        self.thread = Thread(target=self.run)
        self.repos_to_update = {}

    def start(self):
        self.new_updates_event = self.service.express_event(
            "Updates available", "New system updates found.", {})
        self.cancel_event.clear()
        self.thread.start()

    def stop(self):
        self.cancel_event.set()
        self.thread.join()

    def run(self):
        while not self.cancel_event.is_set():
            self.check_updates()
            self.cancel_event.wait(self.UPDATE_CHECK_FREQ)

    def check_updates(self):
        res = []
        all_repos = self.list_repos(CODE_DIR)

        self.update_status("Checking for updates.")
        for count, path in enumerate(all_repos):
            try:
                repo = self.get_repo(path)

                if repo.needs_pull():
                    res.append(repo)
            except GitError as e:
                logger.warning("Unable to fetch %s", path, e)

        if res:
            if self.has_new_updates(res):
                self.repos_to_update = {x.repo_name: x for x in res}
                self.notify_updates()
        else:
            self.update_status("No updates available.")
        return res

    def update_status(self, msg):
        logger.info("UpdateScanner Status: %s", msg)
        self.service.update_status(msg)

    def has_new_updates(self, res):
        keys = {x.repo_name for x in res}
        existing = set(self.repos_to_update.keys())
        return keys - existing

    def notify_updates(self):
        self.update_status("Updates available.")
        self.new_updates_event.fire()

    def list_repos(self, path):
        return [os.path.join(path, x) for x in os.listdir(path)]

    def get_repo(self, path):
        return Repository(path)

    def get_repos_to_update(self):
        return list(self.repos_to_update.values())


class Updater(object):
    def __init__(self, service, scanner):
        self.scanner = scanner
        self.service = service

    def start(self):
        self.service.express_capability("Perform upgrade.",
                                        "Trigger system upgrade.", {},
                                        self.upgrade_handler)

    def upgrade_handler(self):
        repos = self.scanner.get_repos_to_update()
        if not repos:
            self.update_status("No updates available.")
            return

        Thread(target=self.perform_upgrade, args=(repos,)).start()

    def perform_upgrade(self, repos):
        for repo in repos:
            repo.pull(self.send_pull_progress)

        if self.perform_ansible_update():
            self.update_status("Configuration update failed.")
            return

        self.update_status("Configuration complete. Restarting ..")

        self.reboot()

    def reboot(self):
        logger.info("Rebooting..")
        self.update_status("Going down for restart ..")
        reboot_path = os.path.join(SCRIPTS_DIR, "reboot.sh")
        args = [reboot_path]
        with subprocess.Popen(args) as proc:
            proc.wait()
            return proc.returncode

    def perform_ansible_update(self):
        logger.info("Running ansible")
        self.update_status("Updating configurations ..")
        run_ansible_path = os.path.join(SCRIPTS_DIR, "run_ansible.sh")
        args = [run_ansible_path]
        with subprocess.Popen(args) as proc:
            proc.wait()
            return proc.returncode

    def send_pull_progress(self, progress):
        msg = "Update in progress: {}".format(progress * 0.5)
        self.update_status(msg)

    def update_status(self, msg):
        logger.info("Updater status: %s", msg)
        self.service.update_status(msg)


class UpdaterService(EventDrivenService, StatusService,
                     BackgroundProcessServiceStart, BaseService):

    def __init__(self, config):
        self.update_scanner = UpdateScanner(self)
        self.updater = Updater(self, self.update_scanner)
        self.shutdown = Event()
        super().__init__()

    def get_component_name(self):
        return "updater"

    def on_service_start(self, *args, **kwargs):
        super().on_service_start(*args, **kwargs)
        self.update_scanner.start()
        self.updater.start()
        self.notify_start()
        self.shutdown.wait()

    def on_service_stop(self):
        logger.info("Stopping update scanner..")
        self.update_scanner.stop()
        self.shutdown.set()
        super().on_service_stop()
