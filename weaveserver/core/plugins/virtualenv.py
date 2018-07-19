import os
import subprocess

import virtualenv


class VirtualEnvManager(object):
    def __init__(self, path):
        self.venv_home = path

    def install(self, requirements_file=None):
        if os.path.exists(self.venv_home):
            return True

        virtualenv.create_environment(self.venv_home)

        if requirements_file:
            args = [os.path.join(self.venv_home, 'bin/python'), '-m', 'pip',
                    'install', '-r', requirements_file]
            try:
                subprocess.check_call(args)
            except subprocess.CalledProcessError:
                return False

    def activate(self):
        script = os.path.join(self.venv_home, "bin", "activate_this.py")
        execfile(script, dict(__file__=script))

    def deactivate(self):
        pass
