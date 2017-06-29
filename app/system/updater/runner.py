"""
Module contains utility functions to check for updates in repositories and, if necessary, do
a git-pull.
"""

import os
import subprocess
import logging

from git import Repo
from git.util import RemoteProgress


SCRIPTS_DIR = "/home/rpi/scripts"
CODE_DIR = "/home/rpi/Code"

logger = logging.getLogger(__name__)

class PercentProgressIndicator(RemoteProgress):
    """Specialization that calls back a function with a percentage
    indicator"""
    def __init__(self, callback):
        """
        Args:
            callback: function to call when there's an update in
                      progress.
        """
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
        Args:
            path: Path to the git repo.
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

    def environment_vars(self):
        """ Returns a dict containing env-vars for SSH access."""
        return {
            "GIT_SSH_COMMAND": "ssh -i ~/.ssh/id_rsa-" + self.repo_name
        }

    def needs_pull(self):
        """ Wraps a custom environment, does git fetch, and checks whether
        local tip of master is same as that of upstream master."""
        with self.repo.git.custom_environment(**self.environment_vars()):
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
        with self.repo.git.custom_environment(**self.environment_vars()):
            self.clean_untracked()
            self.reset_hard()
            origin = self.repo.remotes.origin
            origin.pull(progress=PercentProgressIndicator(progress_observer))


def check_updates(progress=None):
    """ Iterates through the dirs in CODE_DIR, creates a Repository instance for each
    of them and returns a filtered list with elements for which repository.needs_pull()
    is True.
    """
    res = []
    all_repos = os.listdir(CODE_DIR)

    if not all_repos:
        return []

    logger.info("Checking for updates: %s", str(all_repos))
    for count, path in enumerate(all_repos):
        repo = Repository(os.path.join(CODE_DIR, path))

        if progress is not None:
            progress(count / float(len(all_repos)))

        if repo.needs_pull():
            res.append(repo)

    if progress is not None:
        progress(1.0)

    return res


def run_ansible():
    logger.info("Running ansible")
    run_ansible_path = os.path.join(SCRIPTS_DIR, "run_ansible.sh")
    args = [run_ansible_path]
    with subprocess.Popen(args) as proc:
        proc.wait()
        return proc.returncode

def do_reboot():
    logger.info("Running reboot script..")
    reboot_path = os.path.join(SCRIPTS_DIR, "reboot.sh")
    args = [reboot_path]
    with subprocess.Popen(args)  as proc:
        proc.wait()
        return proc.returncode

