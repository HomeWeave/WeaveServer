import re
import json


def recursive_replace(obj, regex, replace):
    if isinstance(obj, list):
        obj = [recursive_replace(x, regex, replace) for x in obj]
    elif isinstance(obj, dict):
        obj = {k: recursive_replace(x, regex, replace) for k, x in obj.items()}
    elif isinstance(obj, str):
        obj = regex.sub(replace, obj)
    return obj


class ASCIIDecoder(object):
    def preprocess(self, resource, app_info):
        return resource.decode('ascii')


class JSONDecoder(object):
    def preprocess(self, resource, app_info):
        return json.loads(resource)


class JSONEncoder(object):
    def preprocess(self, resource, app_info):
        return json.dumps(resource)


class RegexReplacer(object):
    def __init__(self, find, replace_fn):
        self.regex = re.compile(find)
        self.replace_fn = replace_fn

    def preprocess(self, obj, app_info):
        replace = self.replace_fn(obj, app_info)
        return recursive_replace(obj, self.regex, replace)
