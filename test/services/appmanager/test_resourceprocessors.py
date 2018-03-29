import json

from weaveserver.services.appmanager.resourceprocessors import RegexReplacer
from weaveserver.services.appmanager.resourceprocessors import ASCIIDecoder
from weaveserver.services.appmanager.resourceprocessors import JSONDecoder
from weaveserver.services.appmanager.resourceprocessors import JSONEncoder


class TestASCIIDecoder(object):
    def test_ascii_decode(self):
        text = "test text"

        assert ASCIIDecoder().preprocess(text.encode(), None) == text


class TestJSONDecoder(object):
    def test_json_decode(self):
        obj = {"hello": "world"}
        assert JSONDecoder().preprocess(json.dumps(obj), None) == obj

class TestJSONEncoder(object):
    def test_json_encode(self):
        obj = {"hello": "world"}
        assert JSONEncoder().preprocess(obj, None) == json.dumps(obj)

class TestRegexPreprocessor(object):
    def test_recursive_replacement(self):
        obj = {
            "a": [1, None, 3.4, "$test1"],
            "test": {"x": "$test2", "y": "test3"},
            "inner": {
                "inner2": {
                    "inner3": {
                        "x": "$test-inner"
                    }
                }
            }
        }

        processor = RegexReplacer("^\$test", lambda _, x: x["appid"])
        res = processor.preprocess(obj, {"appid": "hello"})
        assert res == {
            "a": [1, None, 3.4, "hello1"],
            "test": {"x": "hello2", "y": "test3"},
            "inner": {
                "inner2": {
                    "inner3": {
                        "x": "hello-inner"
                    }
                }
            }
        }

