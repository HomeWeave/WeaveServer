from app.core.netutils import ping_host

import pytest


class TestPingHost(object):
    @pytest.mark.skip("Fails on Travis")
    def test_good_host(self):
        assert ping_host("127.0.0.1")

    def test_bad_host(self):
        assert not ping_host("sdlvhsdlkhdfg")
