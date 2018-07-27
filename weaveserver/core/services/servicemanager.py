"""
Contains components that manage services, their sequences and interdependence.
"""

import importlib
import json
import logging
import os
import sys
import threading

from weavelib.services import Module

import weaveserver.services
from weaveserver.core.toposort import toposort
from weaveserver.core.config_loader import get_config

logger = logging.getLogger(__name__)


def list_modules(module):
    res = []
    for name in os.listdir(module.__path__[0]):
        try:
            module = importlib.import_module("weaveserver.services." + name)
            module_meta = module.__meta__
        except ImportError:
            logger.warning("Not a module: services/%s", name)
            continue
        except AttributeError:
            logger.warning("No __meta__ in services/%s.", name)
            continue
        deps = module_meta["deps"]
        res.append(Module(name=name, deps=deps, meta=module_meta,
                          package_path="weaveserver/services/" + name))
        res[-1].system = True
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
    def __init__(self, debug=False, apps=None):
        unsorted_services = list_modules(weaveserver.services)

        if debug:
            for module in unsorted_services:
                logger.info("**DEBUG** App %s: %s", module.name, module.id)

        self.apps = {x.id: x.json() for x in unsorted_services}

        if apps:
            unsorted_services = [x for x in unsorted_services if x.name in apps]

        self.service_modules = topo_sort_modules(unsorted_services)
        self.module_map = {x.name: x for x in unsorted_services}
        self.services = []
        self.active = threading.Event()

    def run(self):
        """ Sequentially starts all the services."""

        core_module = self.module_map["core"]
        if core_module in self.service_modules:
            self.service_modules.remove(core_module)

        error_modules = set()

        self.start_service(core_module, error_modules, apps=self.apps)

        for module in self.service_modules:
            self.start_service(module, error_modules)

        total_services = len(self.service_modules)
        started_services = total_services - len(error_modules)
        logger.info("Started %d out of %d services.",
                    started_services, total_services)
        return started_services, total_services

    def start_service(self, module, error_modules, **kwargs):
        if any(x in error_modules for x in module.deps):
            logger.warning("Not starting %s", module.name)
            error_modules.add(module.name)
            return False

        config = get_config(module.get_config())
        config.update(kwargs)

        service = module.meta["class"](module.id, config)
        service.service_start()

        if not service.wait_for_start(config.get("start_timeout", 10)):
            service.service_stop()
            error_modules.add(module.name)
            logger.info("Failed to start service: %s", module.name)
            return False

        self.services.append(service)
        logger.info("Started service: %s", module.name)
        return True

    def wait(self):
        self.active.wait()

    def start_services(self, services):
        services = set(services)
        new_services = [x for x in self.service_modules if x.name in services]
        self.service_modules = new_services
        return self.run()

    def stop(self):
        self.active.set()
        for service in self.services[::-1]:
            service.service_stop()
