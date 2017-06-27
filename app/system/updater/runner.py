import os
import subprocess

SCRIPTS_DIR = "/home/rpi/scripts"
CODE_DIR = "/home/rpi/Code"

def check_updates():
    update_checker_path = os.path.join(SCRIPTS_DIR, "check_updates.sh")
    args = [update_checker_path, CODE_DIR]
    with subprocess.Popen(args, stdout=subprocess.PIPE) as p:
        return [x.strip() for x in p.stdout]

def do_upgrade(repos):
    updater_path = os.path.join(SCRIPTS_DIR, "update_repos.sh")
    args = [updater_path] + repos
    with subprocess.Popen(args)  as p:
        p.wait()
        #TODO: Update script to exit with non-zero in case of failure.
        return p.returncode

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


