""" Various configuration loaders for services, components and applications. """
import os
import json
import importlib


class BaseConfig(object):
    def __init__(self, config):
        self.config = config

    def __getitem__(self, name):
        return self.config[name]

    def get(self):
        return self.config


class JsonConfig(BaseConfig):
    """ Looks for and parses a JSON file with the given name under configs/, """
    def __init__(self, obj):
        if obj.get("absolute") is True:
            path = obj["file"]
        else:
            path = os.path.join("weaveserver/configs/", obj["path"])
        with open(path) as inp:
            super().__init__(json.load(inp))


class PyConfig(BaseConfig):
    """ Uses a python module for configuration"""
    def __init__(self, config):
        name = config["file"]
        if name.endswith(".py"):
            name = name[:-3]
        else:
            raise ValueError("Not a python file")
        super().__init__(importlib.import_module("weaveserver.configs." + name))

    def __getitem__(self, name):
        return getattr(self.get(), name)


class PropConfig(BaseConfig):
    def __init__(self, config):
        path = os.path.join("weaveserver/configs/", config["path"])
        with open(path) as inp:
            lines = [x.strip().split('=') for x in inp]
        super().__init__({x[0].strip(): x[1].strip() for x in lines})


class SysVarPropConfig(BaseConfig):
    def __init__(self, config):
        path = "/home/rpi/.variables"
        try:
            with open(path) as inp:
                lines = [x.strip().split(':') for x in inp]
            super().__init__({x[0].strip(): x[1].strip() for x in lines})
        except IOError:
            super().__init__({})


class EnvironConfig(BaseConfig):
    def __init__(self, config):
        super().__init__(os.environ)


class ChainedConfig(object):
    def __init__(self, *configs):
        self.configs = configs

    def __getitem__(self, name):
        for config in self.configs:
            try:
                return config[name]
            except KeyError:
                pass
        raise KeyError(name)

    def get(self, key, default=None):
        try:
            return self.__getitem__(key)
        except KeyError:
            return default


def get_simple_loader(name):
    mappings = {
        "json": JsonConfig,
        "pyconfig": PyConfig,
        "property": PropConfig,
        "sysvarfile": SysVarPropConfig,
        "env": EnvironConfig,
    }
    return mappings[name]


def get_config(config):
    res = {}
    for config_item in config:
        key = config_item["name"]
        configs = []
        for loader_info in config_item["loaders"]:
            cls = get_simple_loader(loader_info["type"])
            configs.append(cls(loader_info))
        res[key] = ChainedConfig(*configs)
    return res
