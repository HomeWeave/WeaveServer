"""
Exposes a list of Services where a service is either a full screen app or
background thread.
"""


from .servicemanager import ServiceManager
from .updater_service import UpdaterService
from .hello_service import HelloService
from .webcam_service import WebcamService

SERVICES = [
    UpdaterService,
    #HelloService,
    WebcamService
]

