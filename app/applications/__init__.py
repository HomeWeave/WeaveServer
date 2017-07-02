"""
To write a new app:
    1. Extend the class BaseApplication, import it below, and put it in the
       APPS list below. Please use a folder for each app.
"""

from .bluetooth import BluetoothApp
from .wifi import WifiApp
from .webcam import WebcamApp
from .gmail import GmailApp
from .calendar import CalendarApp
from .updater import UpdaterApp

APPS = [
    BluetoothApp,
    WifiApp,
    WebcamApp,
    GmailApp,
    CalendarApp,
    UpdaterApp
]
