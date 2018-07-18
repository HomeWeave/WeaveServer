import logging
import os
from threading import Thread

from github3 import GitHub

from weavelib.exceptions import ObjectNotFound

from weaveserver.core.plugins import load_plugin_from_path

logger = logging.getLogger(__name__)


def list_plugins(base_dir):
    res = []
    for name in os.listdir(base_dir):
        plugin_info = load_plugin_from_path(base_dir, name)
        if plugin_info:
            res.append(plugin_info)
    return res


def run_plugin(service, timeout):
    service.service_start()
    if not service.wait_for_start(timeout=timeout):
        service.service_stop()
        return False
    return True


def stop_plugin(service):
    service.service_stop()


class PluginManager(object):
    def __init__(self, base_dir, venv_dir, database, appmgr_rpc):
        self.base_dir = base_dir
        self.venv_dir = venv_dir
        self.database = database
        self.appmgr_rpc = appmgr_rpc
        self.enabled_plugins = set()
        self.running_plugins = {}
        self.all_plugins = {}
        self.github_weave_org = GitHub().organization('HomeWeave')

    def start(self):
        self.init_structure(self.base_dir)
        self.init_structure(self.venv_dir)

        try:
            enabled_plugins = self.database["ENABLED_PLUGINS"]
        except KeyError:
            self.database["ENABLED_PLUGINS"] = []
            enabled_plugins = []

        for plugin in list_plugins(self.base_dir):
            self.all_plugins[plugin["id"]] = plugin

        self.enabled_plugins = set(self.all_plugins) & set(enabled_plugins)

        thread = Thread(target=self.start_async, args=(self.enabled_plugins,))
        thread.start()

    def start_async(self, enabled_plugins):
        for plugin_id in enabled_plugins:
            self.activate(plugin_id)

        logger.info("Started %d of %d plugins.", len(self.running_plugins),
                    len(self.all_plugins))

    def stop(self):
        for id, service in self.running_plugins.items():
            stop_plugin(service)

    def init_structure(self, path):
        if not os.path.isdir(path):
            try:
                os.makedirs(path)
            except:
                pass
            if not os.path.isdir(path):
                raise Exception("Unable to create directory: " + path)

    def list_installed_plugins(self):
        def transform(plugin):
            return {
                "id": plugin["id"],
                "name": plugin["name"],
                "description": plugin["description"],
                "enabled": plugin["id"] in self.enabled_plugins
            }

        return [transform(x) for x in self.all_plugins]

    def list_available_plugins(self):
        res = []
        for repo in self.github_weave_org.repositories():
            contents = repo.directory_contents("/", return_as=dict)
            if "plugin.json" in contents:
                res.append({
                    "url": repo.clone_url,
                    "description": repo.description,
                    "enabled": False,
                })
        return res

    def activate(self, id):
        try:
            plugin = self.all_plugins[id]
        except KeyError:
            raise ObjectNotFound(id)

        if id in self.running_plugins:
            return True

        service = plugin.get_module()
        if not run_plugin(service, timeout=plugin["start_timeout"]):
            return False

        logger.info("Started plugin: %s", plugin.dest)
        self.running_plugins[id] = service

        # TODO: RPC call to core to register token.
        return True

    def deactivate(self, id):
        pass
