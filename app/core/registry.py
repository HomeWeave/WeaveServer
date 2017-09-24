""" App-wide registry """


class Registry(object):
    def __init__(self):
        self.registry = {}

    def query(self, name):
        return self.registry.get(name)

    def register(self, name, obj):
        if name not in self.registry:
            self.registry[name] = obj
            return True
        return False
