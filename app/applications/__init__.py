"""
To write a new app:
    1. Extend the class BaseApplication,
    2. Put the Class in the APPS list below
"""

from .bluetooth import BluetoothApp
from .wifi import WifiApp
from .webcam import WebcamApp
from .gmail import GmailApp
from .calendar import CalendarApp
from .updater import UpdaterApp
from .shell import ShellApp

APPS = [
    BluetoothApp,
    WifiApp,
    WebcamApp,
    GmailApp,
    CalendarApp,
    UpdaterApp
]
