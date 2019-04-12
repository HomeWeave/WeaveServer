import pytest

from weavelib.exceptions import ProtocolError

from messaging.messaging_utils import get_required_field


class TestUtils(object):
    def test_get_required_field_simple(self):
        assert get_required_field({"test": "x"}, "test") == "x"

    def test_get_required_field_invalid_key(self):
        with pytest.raises(ProtocolError):
            assert get_required_field({}, "test")
