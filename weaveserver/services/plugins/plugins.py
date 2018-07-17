import importlib
import hashlib
import json
import logging
import os
import shutil
import sys
from threading import Thread

import git
from github3 import GitHub

from weavelib.exceptions import ObjectNotFound

from .virtualenv import VirtualEnvManager

logger = logging.getLogger(__name__)


def list_plugins(base_dir):
    res = []
    for name in os.listdir(base_dir):
        try:
            with open(os.path.join(base_dir, name, "plugin.json")) as inp:
                plugin_info = json.load(inp)
        except IOError:
            logger.warning("Error opening plugin.json within %s", name)
            continue
        except ValueError:
            logger.warning("Error parsing plugin.json within %s", name)
            continue

        try:
            sys.path.append(os.path.join(base_dir, name))
            module = importlib.import_module(plugin_info["service"])
            module_meta = module.__meta__
        except ImportError:
            logger.warning("Failed to import dependencies for %s", name)
            continue
        except KeyError:
            logger.warning("Required field not found in %s/plugin.json.", name)
            continue
        finally:
            sys.path.pop(-1)

        plugin = create_plugin(os.path.join(base_dir, name))
        plugin_id = plugin.unique_id()
        deps = module_meta["deps"]
        res.append(dict(name=name, deps=deps, meta=module_meta, id=plugin_id,
                        package_path=plugin_info["service"]))
    return res


def create_plugin(path):
    if os.path.isdir(os.path.join(path, '.git')):
        return GitPlugin(None, path)
    return FilePlugin(path, path)


def run_plugin(service):
    pass


def stop_plugin(service):
    pass


class BasePlugin(object):
    def __init__(self, src, dest, venv_base_path):
        self.src = src
        self.dest = dest
        self.plugin_dir = self.get_plugin_dir()
        self.venv_manager = VirtualEnvManager()

    def get_plugin_dir(self):
        return os.path.join(self.dest, self.unique_id())

    def unique_id(self):
        return hashlib.md5(self.src.encode('utf-8')).hexdigest()

    def needs_create(self):
        return not os.path.isdir(self.plugin_dir)


class GitPlugin(BasePlugin):
    def __init__(self, src, dest):
        if src is None:
            self.git = git.Repo(dest)
            self.src = next(self.git.remote('origin').urls)
        super(GitPlugin, self).__init__(self.src, dest)

    def create(self):
        git.Repo.clone_from(self.src, self.plugin_dir)


class FilePlugin(BasePlugin):
    def create(self):
        shutil.copytree(self.src, self.plugin_dir)


class PluginManager(object):
    PLUGIN_TYPES = {
        "git": GitPlugin,
        "file": FilePlugin,
    }

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
        if not run_plugin(service):
            return False

        logger.info("Started plugin: %s", plugin.dest)
        self.running_plugins[id] = service
        return True

    def deactivate(self, id):
        pass
