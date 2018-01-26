import importlib
import hashlib
import json
import logging
import os
import shutil
import sys

import git


logger = logging.getLogger(__name__)


class BasePlugin(object):
    def __init__(self, src, dest):
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
        self.repo = git.Repo.clone_from(self.src, self.plugin_dir)


class FilePlugin(object):
    def create(self):
        shutil.copytree(self.sec, self.plugin_dir)


class PluginManager(object):
    BASE_DIR = os.path.expanduser("~/.rpi/modules")
    PLUGIN_TYPES = {
        "git": GitPlugin,
        "file": FilePlugin,
    }

    def __init__(self):
        self.init_structure(self.BASE_DIR)

    def list_modules(self):
        sys.path.insert(0, self.BASE_DIR)
        for name in os.listdir(self.BASE_DIR):
            try:
                module = importlib.import_module(name)
            except ImportError:
                logger.warning("Failed to import module: %s", name)
                continue
            except AttributeError:
                logger.warning("No __meta__ in services/%s.", name)
                continue
            deps = module.__meta__["deps"]
            res.append(Module(name=name, deps=deps, meta=module.__meta__))

    def init_structure(self, path):
        if not os.path.isdir(path):
            try:
                os.makedirs(path)
            except:
                pass
            if not os.path.isdir(path):
                raise Exception("Unable to create 'modules' directory.")

        list_file = os.path.join(path, "modules.txt")
        if not os.path.isfile(list_file):
            with open(list_file) as f:
                f.write("")

    def list_enabled_repos(self, path):
        with open(path) as config_file:
            obj = json.load(config_file)
        for repo_info in obj:
            if not repo_info.get("enabled", True):
                continue
            if not self.PLUGIN_TYPES.get(repo_info.get("type")):
                logger.warning("Plugin type invalid. Skipping.")
                continue
