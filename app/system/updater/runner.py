import os
import subprocess

from git import Repo
from git.util import RemoteProgress


SCRIPTS_DIR = "/home/rpi/scripts"
CODE_DIR = "/home/rpi/Code"

class PercentProgressIndicator(RemoteProgress):
    def __init__(self, callback):
        self.callback = callback
        super().__init__()

    def update(self, op, cur_count, max_count=None, msg=""):
        if max_count is not None:
            self.callback(0)
        else:
            self.callback(cur_count / float(max_count))


class Repository(object):
    def __init__(self, path):
        self.path = path
        self.repo_name = os.path.basename(path)
        self.repo = Repo(self.path)

    def clean_untracked(self):
        self.repo.git.clean("-dfx")

    def reset_hard(self):
        self.repo.git.reset('--hard')

    def environment_vars(self):
        return {
            "GIT_SSH_COMMAND": "ssh -i ~/.ssh/id_rsa-" + self.repo_name
        }

    def needs_pull(self):
        with self.repo.git.custom_environment(**self.environment_vars()):
            for remote in self.repo.remotes:
                remote.fetch()

            for x in self.repo.iter_commits('master..origin/master'):
                return True
            return False

    def pull(self, progress_observer=None):
        with self.repo.git.custom_environment(**self.environment_vars()):
            self.clean_untracked()
            self.reset_hard()
            origin = self.repo.remotes.origin
            origin.pull(progress=PercentProgressIndicator(progress_observer))


def check_updates(progress=None):
    res = []
    all_repos = os.listdir(CODE_DIR)

    if not all_repos:
        return []

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
    run_ansible_path = os.path.join(SCRIPTS_DIR, "run_ansible.sh")
    args = [run_ansible_path]
    with subprocess.Popen(args) as p:
        p.wait()
        return p.returncode

def do_reboot():
    reboot_path = os.path.join(SCRIPTS_DIR, "reboot.sh")
    args = [reboot_path]
    with subprocess.Popen(args)  as p:
        p.wait()
        #TODO: Update script to exit with non-zero in case of failure.
        return p.returncode


