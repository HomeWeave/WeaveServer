import pytest
from jsonschema import validate

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

    def test_arg_from_bad_info(self):
        with pytest.raises(ValueError):
            KeywordParameter.from_info({})

        with pytest.raises(ValueError):
            ArgParameter.from_info({})


class TestAPI(object):
    def test_validate_schema_without_args(self):
        api = API("name", "desc", [])
        obj = {"command": "name", "id": ""}

        assert validate(obj, api.schema) is None

        api.validate_call()

        with pytest.raises(TypeError):
            api.validate_call(1, 2, 3, k=5)

    def test_validate_schema_with_args(self):
        api = API("name", "desc", [
            ArgParameter("a1", "d1", str),
            KeywordParameter("a2", "d2", int),
            ArgParameter("a3", "d3", bool),
        ])

        api.validate_call("a1", False, a2=5)

        with pytest.raises(TypeError):
            api.validate_call()

        with pytest.raises(TypeError):
            api.validate_call("a", True, {1: 2}, a4=5)

    def test_info(self):
        api = API("name", "desc", [
            KeywordParameter("a2", "d2", int),
            ArgParameter("a1", "d1", str),
            KeywordParameter("a3", "d3", bool),
        ])

        assert api.info == {
            "name": "name",
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
        obj.pop("id")
        assert obj == {
            "command": "name",
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

    def test_api_reconstruct_without_args(self):
        api = API("name", "desc", [])
        assert API.from_info(api.info).info == api.info

    def test_api_bad_reconstruct(self):
        with pytest.raises(ValueError):
            API.from_info({})
