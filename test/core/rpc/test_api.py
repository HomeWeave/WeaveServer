import pytest
from jsonschema import validate, ValidationError

from app.core.rpc.api import API, ArgParameter, KeywordParameter


class TestParameter(object):
    def test_bad_type(self):
        with pytest.raises(ValueError):
            ArgParameter("", "", dict)

    def test_schema(self):
        assert {"type": "string"} == ArgParameter("", "", str).schema
        assert {"type": "number"} == ArgParameter("", "", int).schema
        assert {"type": "boolean"} == KeywordParameter("", "", bool).schema

    def test_info(self):
        assert ArgParameter("a", "b", str).info == {
            "name": "a",
            "description": "b",
            "type": "text"
        }

    def test_arg_parameter_from_info(self):
        obj = {
            "name": "a",
            "description": "b",
            "type": "text"
        }
        assert ArgParameter.from_info(obj).info == obj


class TestAPI(object):
    def test_validate_schema_without_args(self):
        api = API("name", "desc", [])
        obj = {"command": api.id}

        assert validate(obj, api.schema) is None

        with pytest.raises(ValidationError):
            validate({"command": api.id, "args": {}}, api.schema)

    def test_validate_schema_with_args(self):
        api = API("name", "desc", [
            ArgParameter("a1", "d1", str),
            KeywordParameter("a2", "d2", int),
            ArgParameter("a3", "d3", bool),
        ])

        obj = {
            "command": api.id,
            "args": ["string", False],
            "kwargs": {"a2": 5},
        }
        assert validate(obj, api.schema) is None

        with pytest.raises(ValidationError):
            validate({"command": "uid"}, api.schema)

        with pytest.raises(ValidationError):
            validate({"command": "uid", "args": dict(a1="a", a2="", a3=True)},
                     api.schema)

    def test_info(self):
        api = API("name", "desc", [
            KeywordParameter("a2", "d2", int),
            ArgParameter("a1", "d1", str),
            KeywordParameter("a3", "d3", bool),
        ])

        assert api.info == {
            "name": "name",
            "id": api.id,
            "description": "desc",
            "args": [x.info for x in api.args],
            "kwargs": {p.name: p.info for p in api.kwargs}
        }

    def test_validate_call(self):
        api = API("name", "desc", [
            KeywordParameter("a2", "d2", int),
            ArgParameter("a1", "d1", str),
            KeywordParameter("a3", "d3", bool),
        ])

        obj = api.validate_call("str", a2=5, a3=False)
        assert obj == {
            "command": api.id,
            "args": ["str"],
            "kwargs": {"a2": 5, "a3": False}
        }

    def test_api_reconstruct(self):
        api = API("name", "desc", [
            KeywordParameter("a2", "d2", int),
            ArgParameter("a1", "d1", str),
            KeywordParameter("a3", "d3", bool),
        ])

        assert API.from_info(api.info).info == api.info
