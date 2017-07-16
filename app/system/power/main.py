import os
import subprocess
import logging


SCRIPTS_DIR = "/home/rpi/scripts"

logger = logging.getLogger(__name__)

def do_reboot():
    logger.info("Running reboot script..")
    reboot_path = os.path.join(SCRIPTS_DIR, "reboot.sh")
    args = [reboot_path]
    with subprocess.Popen(args)  as proc:
        proc.wait()
        return proc.returncode

def do_poweroff():
    logger.info("Running reboot script..")
    shutdown_path = os.path.join(SCRIPTS_DIR, "shutdown.sh")
    args = [shutdown_path]
    with subprocess.Popen(args)  as proc:
        proc.wait()
        return proc.returncode

