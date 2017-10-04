"""
To write a new app:
    1. Extend the class BaseApplication,
    2. Put the Class in the APPS list below
"""

from .updater import UpdaterApp
from .shell import ShellApp
from .power import SystemPowerApp

APPS = [
    UpdaterApp,
    SystemPowerApp
]
