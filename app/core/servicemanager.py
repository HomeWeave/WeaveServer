"""
Contains components that manage services, their sequences and interdependence.
"""

import importlib
import logging
import os
import time
from collections import namedtuple

import app.services
from app.core.toposort import toposort
from app.core.config_loader import get_config

logger = logging.getLogger(__name__)
Module = namedtuple('Module', ["name", "deps", "meta"])


def list_modules(module):
    res = []
    for name in os.listdir(module.__path__[0]):
        module = importlib.import_module("app.services." + name)
        module_meta = module.__meta__
        deps = module_meta["deps"]
        res.append(Module(name=name, deps=deps, meta=module_meta))
    return res


def topo_sort_modules(modules):
    module_map = {x.name: x for x in modules}
    dep_map = {x.name: x.deps for x in modules}
    res = []
    for item in toposort(dep_map):
        res.append(module_map[item])
    return res


class ServiceManager(object):
    """
    Scans for all service modules within the given module.
    """
    def __init__(self, registry):
        unsorted_services = list_modules(app.services)
        self.service_modules = topo_sort_modules(unsorted_services)
        self.services = []

    def run(self):
        """ Sequentially starts all the services."""
        for module in self.service_modules:
            config = get_config(module.meta.get("config", []))
            service = module.meta["class"](config)

            service.service_start()
            self.services.append(service)
            print("Started:", service)

        while True:
            print("waiting..")
            time.sleep(60)

    def stop(self):
        for service in self.services[::-1]:
            print("Stopping", service)
            service.service_stop()
