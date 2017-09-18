"""
Contains components that manage services, their sequences and interdependence.
"""

import importlib
import logging
from collections import namedtuple

from app.core.toposort import toposort

logger = logging.getLogger(__name__)
Module = namedtuple('Module', ["name", "deps", "meta"])


def list_modules(module):
    res = []
    # for name in os.listdir(module.__path__):
    for name in ["messaging"]:
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


class ServiceManager(threading.Thread):
    """
    Sequentially starts services using service.service_start(). When a new
    service is activated, view_manager is updated with its view.
    """
    def __init__(self, services, socket_manager):
        self.services = services
        self.cur_service = None
        self.socket_manager = socket_manager
        super().__init__()

    def run(self):
        """ Sequentially starts all the services."""
        logger.info("Starting services...")
        for service_cls in self.services:
            self.cur_service = service_cls(self.socket_manager)
            self.cur_service.service_start()

