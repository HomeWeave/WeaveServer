"""
Exposes a list of Services where a service is either a full screen app or
background thread.
"""


from .shell_service import ShellService
from .bluetooth.service import BluetoothService


SERVICES = [
    ShellService
]

