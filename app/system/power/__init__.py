
from .main import do_reboot
from .main import do_poweroff

EXPORTS = [
    (do_reboot, "reboot", "power"),
    (do_poweroff, "power_off", "power"),
]
