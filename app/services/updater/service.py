import logging
import os
import subprocess
from threading import Timer

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

    def __init__(self, notification_queue, update_status_queue):
        self.notification_sender = Sender(notification_queue)
        self.update_status_sender = Sender(update_status_queue)
        self.timer = Timer(self.UPDATE_CHECK_FREQ, self.check_updates)

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

            self.checking_updates_progress(repo, count / float(len(all_repos)))

            if repo.needs_pull():
                res.append(repo)
        self.checking_updates_progress(1.0)
        return res

    def checking_updates_progress(self, repo, progress):
        self.update_status_sender.send(Task({
            "status": "FETCH",
            "progress": progress,
            "repo": repo.repo_name
        }))

    def notify_updates(self):
        self.notification_sender.send(Task({"message": "Update available."}))


class UpdaterService(BackgroundProcessServiceStart, BaseService):
    def __init__(self, config):
        self.update_scanner = UpdateScanner("/shell/notifications",
                                            "/app/services/updater/status")
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
