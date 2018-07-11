import importlib
import hashlib
import json
import logging
import os
import shutil
import sys
from uuid import uuid4

import git
from weavelib.db import AppDBConnection


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

        deps = module_meta["deps"]
        res.append(dict(name=name, deps=deps, meta=module_meta,
                        package_path=plugin_info["service"]))
    return res


class BasePlugin(object):
    def __init__(self, src, dest):
        self.plugin_id = str(uuid4())
        self.src = src
        self.dest = dest
        self.plugin_dir = self.get_plugin_dir()

    def get_plugin_dir(self):
        sig = hashlib.md5(self.src.encode("utf-8")).hexdigest()
        basename = "{}-{}".format(os.path.basename(self.src), sig)
        return os.path.join(self.dest, basename)

    def needs_create(self):
        return not os.path.isdir(self.plugin_dir)


class GitPlugin(BasePlugin):
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

    def __init__(self, base_dir, database):
        self.base_dir = base_dir
        self.database = database

    def start(self):
        self.init_structure(self.base_dir)

    def stop(self):
        pass

    def list_installed_plugins(self):
        try:
            enabled_plugins = self.database["ENABLED_PLUGINS"]
        except KeyError:
            enabled_plugins = []

        all_plugins = list_plugins(self.base_dir)
        for plugin_info in all_plugins:
            plugin_info["enabled"] = plugin_info["id"] in enabled_plugins

        return all_plugins

    def init_structure(self, path):
        if not os.path.isdir(path):
            try:
                os.makedirs(path)
            except:
                pass
            if not os.path.isdir(path):
                raise Exception("Unable to create plugins directory.")

    def activate(self, id):
        pass

    def deactivate(self, id):
        pass
