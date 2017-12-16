import pytest
from jsonschema import validate, ValidationError

from app.core.services.api import Parameter, API


class TestParameter(object):
    def test_bad_type(self):
        with pytest.raises(ValueError):
            Parameter("", "", dict)

    def test_schema(self):
        assert {"type": "string"} == Parameter("", "", str).schema
        assert {"type": "number"} == Parameter("", "", int).schema
        assert {"type": "boolean"} == Parameter("", "", bool).schema

    def test_info(self):
        assert Parameter("a", "b", str).info == {
            "name": "a",
            "description": "b",
            "type": "text"
        }


class TestAPI(object):
    def test_validate_schema_without_args(self):
        api = API("uid", "name", "desc")
        obj = {"command": "uid"}

        assert validate(obj, api.schema) is None

        with pytest.raises(ValidationError):
            validate({"command": "uid", "args": {}}, api.schema)

    def test_validate_schema_with_args(self):
        api = API("uid", "name", "desc", [
            Parameter("a1", "d1", str),
            Parameter("a2", "d2", int),
            Parameter("a3", "d3", bool),
        ])

        obj = {
            "command": "uid",
            "args": {
                "a1": "string",
                "a2": 5,
                "a3": False
            }
        }
        assert validate(obj, api.schema) is None

        with pytest.raises(ValidationError):
            validate({"command": "uid"}, api.schema)

        with pytest.raises(ValidationError):
            validate({"command": "uid", "args": dict(a1="a", a2="", a3=True)},
                     api.schema)

    def test_info(self):
        api = API("uid", "name", "desc", [
            Parameter("a1", "d1", str),
            Parameter("a2", "d2", int),
            Parameter("a3", "d3", bool),
        ])

        assert api.info == {
            "name": "name",
            "id": "uid",
            "description": "desc",
            "parameters": {p.name: p.info for p in api.parameters}
        }
