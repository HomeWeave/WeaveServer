import os
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
