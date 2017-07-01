"""
Exposes a list of Services where a service is either a full screen app or
background thread.
"""


#from .updater_service import UpdaterService
from .shell_service import ShellService


SERVICES = [
    #UpdaterService,
    ShellService
]

