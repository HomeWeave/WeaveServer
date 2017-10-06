import logging
import os
import subprocess
from threading import Timer, Thread

from git import Repo
from git.util import RemoteProgress
from retask import Task

from app.core.messaging import Receiver, Sender
from app.core.service_base import BaseService, BackgroundProcessServiceStart


logger = logging.getLogger(__name__)
SCRIPTS_DIR = "/home/rpi/scripts"
CODE_DIR = "/home/rpi/Code"


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

    def __init__(self, notification_queue):
        self.notification_sender = Sender(notification_queue)
        self.timer = Timer(self.UPDATE_CHECK_FREQ, self.check_updates)
        self.repos_to_update = []

    def start(self):
        self.timer.start()

    def stop(self):
        pass

    def check_updates(self):
        res = []
        all_repos = os.listdir(CODE_DIR)

        if not all_repos:
            return []

        logger.info("Checking for updates: %s", str(all_repos))
        for count, path in enumerate(all_repos):
            repo = Repository(os.path.join(CODE_DIR, path))

            if repo.needs_pull():
                res.append(repo)
        self.repos_to_update = res
        return res

    def notify_updates(self):
        self.notification_sender.send(Task({"message": "Update available."}))

    @property
    def updates(self):
        return self.repos_to_update


class Updater(Receiver):
    def __init__(self, scanner, queue_name):
        super().__init__(queue_name)
        self.scanner = scanner
        self.receiver_thread = Thread(target=self.run)

    def start(self):
        self.start()
        self.receiver_thread.start()

    def on_message(self, msg):
        repos = self.scanner.updates
        if not repos:
            self.update_status("No Updates found.")
            return

        for repo in repos:
            repo.pull(self.send_pull_progress)

        self.run_ansible()

    def run_ansible(self):
        pass

    def send_pull_progress(self, progress):
        task = Task({
            "status": "Updating..",
            "stage": 1,
            "total_stages": 2,
            "progress": progress
        })
        self.status_sender.send(task)


class UpdaterService(BackgroundProcessServiceStart, BaseService):
    def __init__(self, config):
        self.update_scanner = UpdateScanner("/shell/notifications")
        self.updater = Updater("/app/services/updater")
        super().__init__()

    def get_component_name(self):
        return "updater"

    def on_service_start(self, *args, **kwargs):
        self.notify_start()

    def perform_update(self):
        logger.info("Running ansible")
        run_ansible_path = os.path.join(SCRIPTS_DIR, "run_ansible.sh")
        args = [run_ansible_path]
        with subprocess.Popen(args) as proc:
            proc.wait()
            return proc.returncode

    def on_service_stop(self):
        self.update_scanner.stop()
