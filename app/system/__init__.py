from collections import defaultdict

from .updater import EXPORTS as UPDATER_EXPORTS
from .power import EXPORTS as POWER_EXPORTS


ALL_MODULES = UPDATER_EXPORTS + POWER_EXPORTS

class ModuleManager(object):
    def __init__(self):
        self.modules = {}
        for func, name, perm in ALL_MODULES:
            self.modules[name] = (func, perm)

    def get(self, app, name):
        # Todo: Check permissions here.
        return self.modules[name][0]

