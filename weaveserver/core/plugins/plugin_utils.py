import importlib
import hashlib
import json
import logging
import os
import shutil
import sys
from uuid import uuid4

import git


logger = logging.getLogger(__name__)


class BasePlugin(object):
    def __init__(self, src, dest):
        self.src = src
        self.dest = dest
        self.plugin_dir = self.get_plugin_dir()
        self.appid = "plugin-token-" + str(uuid4())

    def get_plugin_dir(self):
        return os.path.join(self.dest, self.unique_id())

    def unique_id(self):
        return hashlib.md5(self.src.encode('utf-8')).hexdigest()

    def json(self):
        return {
            "appid": "app-token-" + self.appid,
            "package": self.dest.replace("/", ".")
        }

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


def create_plugin(path):
    if os.path.isdir(os.path.join(path, '.git')):
        return GitPlugin(None, path)
    return FilePlugin(path, path)


def load_plugin_from_path(base_dir, name):
    try:
        with open(os.path.join(base_dir, name, "plugin.json")) as inp:
            plugin_info = json.load(inp)
    except IOError:
        logger.warning("Error opening plugin.json within %s", name)
        return None
    except ValueError:
        logger.warning("Error parsing plugin.json within %s", name)
        return None

    try:
        sys.path.append(os.path.join(base_dir, name))
        module = importlib.import_module(plugin_info["service"])
    except ImportError:
        logger.warning("Failed to import dependencies for %s", name)
        return None
    except KeyError:
        logger.warning("Required field not found in %s/plugin.json.", name)
        return None
    finally:
        sys.path.pop(-1)

    plugin = create_plugin(os.path.join(base_dir, name))
    return {
        "plugin": plugin,
        "cls": module,
        "name": name,
        "deps": plugin_info.get("deps"),
        "id": plugin.unique_id(),
        "package_path": plugin_info["service"],
        "config": plugin_info.get("config", {}),
        "start_timeout": plugin_info.get("start_timeout", 30)
    }


def install_plugin_from_source(cls, src, dest):
    plugin = cls(src, dest)
    plugin.create()

    dir_name = os.path.basename(plugin.get_plugin_dir())
    return load_plugin_from_path(dest, dir_name)
