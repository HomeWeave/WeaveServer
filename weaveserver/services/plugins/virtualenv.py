
class VirtualEnvManager(object):
    def __init__(self, path):
        self.path = path

    def install_requirements(self):
        self.activate()

    def activate(self):
        pass

    def deactivate(self):
        pass
