from app.core.netutils import ping_host


class TestPingHost(object):
    def test_good_host(self):
        assert ping_host("localhost")

    def test_bad_host(self):
        assert not ping_host("sdlvhsdlkhdfg")
