import importlib
import subprocess
import sys


class BackgroundAppLauncher(object):
    def __init__(self, base_module="app.applications"):
        self.base_module = base_module
        self.processes = {}

    def launch(self, name):
        commands = [sys.executable, "launch-app", name]
        proc = subprocess.Popen(commands)
        self.processes[proc.pid] = proc


def handle_launch(name):
    module = importlib.import_module("app.applications." + name)
    meta = module.__meta__

    cls = meta["background_app_class"]
    app = cls()
    app.run()
