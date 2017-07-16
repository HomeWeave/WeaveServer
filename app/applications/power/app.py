import logging

from app.core.base_app import BaseApp, BaseCommandsListener
from app.core.base_app import BaseWebSocket

logger = logging.getLogger(__name__)


class SystemPowerCommandsListener(BaseCommandsListener):
    COMMANDS = [
        {
            "name": "Shutdown",
            "cmd": "shutdown"
        },
        {
            "name": "Reboot",
            "cmd": "reboot"
        },
    ]

    def __init__(self, app):
        self.app = app

    def on_command(self, command):
        func = getattr(self.app, "handle_" + command.lower(), None)
        if func is None:
            return None
        func()
        return "OK"

    def list_commands(self):
        return self.COMMANDS


class SystemPowerApp(BaseApp):
    NAME = "Power"
    DESCRIPTION = "Power off or reboot system"
    ICON = "fa-power-off"

    def __init__(self, service, socketio):
        self.service = service
        self.listener = SystemPowerCommandsListener(self)
        super().__init__(BaseWebSocket("/null", socketio), self.listener)

        self.power_off = service.api(self, "power_off")
        self.reboot = service.api(self, "reboot")

    def handle_shutdown(self):
        self.power_off()

    def handle_reboot(self):
        self.reboot()

    def html(self):
        with open(self.get_file("static/index.html")) as inp:
            return inp.read()

    def on_command(self, command):
        return self.listener.on_command(command)

    def list_commands(self):
        return self.listener.list_commands()
