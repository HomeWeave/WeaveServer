import importlib
import hashlib
import json
import logging
import os
import shutil
import sys

import git
from github3 import GitHub

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
    else:
        return FilePlugin(path, path)


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

    def __init__(self, base_dir, venv_dir, database):
        self.base_dir = base_dir
        self.venv_dir = venv_dir
        self.database = database
        self.enabled_plugins = []
        self.github_weave_org = GitHub().organization('HomeWeave')

    def start(self):
        self.init_structure(self.base_dir)
        self.init_structure(self.venv_dir)

        try:
            self.enabled_plugins = self.database["ENABLED_PLUGINS"]
        except KeyError:
            self.database["ENABLED_PLUGINS"] = []
            self.enabled_plugins = []

    def stop(self):
        pass

    def init_structure(self, path):
        if not os.path.isdir(path):
            try:
                os.makedirs(path)
            except:
                pass
            if not os.path.isdir(path):
                raise Exception("Unable to create directory: " + path)

    def list_installed_plugins(self):
        all_plugins = list_plugins(self.base_dir)
        for plugin_info in all_plugins:
            plugin_info["enabled"] = plugin_info["id"] in self.enabled_plugins

        return all_plugins

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
        pass

    def deactivate(self, id):
        pass
