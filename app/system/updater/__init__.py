"""
Brings check_updates, run_ansible, do_reboot to the module level.
"""

from .runner import check_updates
from .runner import run_ansible
from .runner import do_update

EXPORTS = [
    (check_updates, "check_updates", "updater"),
    (do_update, "update", "updater"),
    (run_ansible, "reconfigure", "updater"),
]
