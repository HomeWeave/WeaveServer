import os
import subprocess
from tempfile import TemporaryDirectory

from weaveserver.core.plugins import VirtualEnvManager


class TestVirtualEnvManager(object):
    def setup_method(self):
        self.tempdir = TemporaryDirectory()

    def teardown_method(self):
        self.tempdir.cleanup()

    def test_install(self):
        venv = VirtualEnvManager(os.path.join(self.tempdir.name, "1"))
        venv.install()

        assert os.path.isdir(os.path.join(self.tempdir.name, "1"))
        assert os.path.isfile(os.path.join(self.tempdir.name, "1/bin/python"))

    def test_install_requirements(self):
        requirements_file = os.path.join(self.tempdir.name, 'requirements.txt')

        with open(requirements_file, 'w') as out:
            out.write('bottle')

        venv = VirtualEnvManager(os.path.join(self.tempdir.name, "2"))
        venv.install(requirements_file=requirements_file)

        cmd = [
            os.path.join(self.tempdir.name, "2/bin/python"),
            "-c"
            "import bottle"
        ]
        assert subprocess.call(cmd) == 0

    def test_install_bad_requirements_file(self):
        requirements_file = os.path.join(self.tempdir.name, 'invalid.txt')

        venv = VirtualEnvManager(os.path.join(self.tempdir.name, "3"))
        assert not venv.install(requirements_file=requirements_file)

    def test_install_bad_dependencies(self):
        requirements_file = os.path.join(self.tempdir.name, 'requirements.txt')

        with open(requirements_file, 'w') as out:
            out.write('some-random-package-that-doesnt-exist')

        venv = VirtualEnvManager(os.path.join(self.tempdir.name, "4"))
        assert not venv.install(requirements_file=requirements_file)
