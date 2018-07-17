import os

import pip
import virtualenv


class VirtualEnvManager(object):
    def __init__(self, path):
        self.venv_home = path

    def install(self, requirements_file=None):
        if not os.path.exists(self.venv_home):
            virtualenv.create_environment(self.venv_home)

        if requirements_file:
            pip.main(["install", "-r", requirements_file,
                      "--prefix", self.venv_home])

    def activate(self):
        script = os.path.join(self.venv_home, "bin", "activate_this.py")
        execfile(script, dict(__file__=script))

    def deactivate(self):
        pass
