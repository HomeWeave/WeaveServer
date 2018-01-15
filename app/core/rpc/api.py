from uuid import uuid4

from jsonschema import validate, ValidationError


class Parameter(object):
    def __init__(self, name, desc, cls):
        if cls not in (str, int, bool):
            raise ValueError("Unexpected type for parameter.")

        self.name = name
        self.desc = desc
        self.cls = cls
        self.param_type = {str: "text", int: "number", bool: "toggle"}[cls]
        self.schema_type = {str: "string", int: "number", bool: "boolean"}[cls]

    @property
    def schema(self):
        return {"type": self.schema_type}

    @property
    def info(self):
        return {
            "name": self.name,
            "description": self.desc,
            "type": self.param_type
        }


class ArgParameter(Parameter):
    positional = True

    @staticmethod
    def from_info(info):
        try:
            cls = {"text": str, "number": int, "toggle": bool}[info["type"]]
            return ArgParameter(info["name"], info["description"], cls)
        except KeyError:
            raise ValueError("Invalid ArgParameter info object.")


class KeywordParameter(Parameter):
    positional = False

    @staticmethod
    def from_info(info):
        try:
            cls = {"text": str, "number": int, "toggle": bool}[info["type"]]
            return KeywordParameter(info["name"], info["description"], cls)
        except KeyError:
            raise ValueError("Invalid KeywordParameter info object.")


class API(object):
    def __init__(self, name, desc, params):
        self.name = name
        self.description = desc
        self.args = [x for x in params if x.positional]
        self.kwargs = [x for x in params if not x.positional]

    @property
    def schema(self):
        obj = {
            "type": "object",
            "properties": {
                "command": {"enum": [self.name]},
                "id": {"type": "string"},
            },
            "additionalProperties": False,
            "required": ["command", "id"],
        }

        if self.args:
            obj["properties"]["args"] = {
                "type": "array",
                "items": [p.schema for p in self.args],
                "minItems": len(self.args),
                "maxItems": len(self.args)
            }
            obj["required"].append("args")

        if self.kwargs:
            obj["properties"]["kwargs"] = {
                "type": "object",
                "properties": {p.name: p.schema for p in self.kwargs},
                "required": [p.name for p in self.kwargs]
            }
            obj["required"].append("kwargs")

        return obj

    @property
    def info(self):
        return {
            "name": self.name,
            "description": self.description,
            "args": [x.info for x in self.args],
            "kwargs": {x.name: x.info for x in self.kwargs}
        }

    def validate_call(self, *args, **kwargs):
        obj = {"command": self.name, "id": "invocation-" + str(uuid4())}
        if args:
            obj["args"] = list(args)
        if kwargs:
            obj["kwargs"] = kwargs

        try:
            validate(obj, self.schema)
        except ValidationError:
            raise TypeError("Bad parameters for function call.")

        return obj

    @staticmethod
    def from_info(info):
        try:
            api = API(info["name"], info["description"], [])
        except KeyError:
            raise ValueError("Invalid API info object.")

        api.args = [ArgParameter.from_info(x) for x in info.get("args", [])]
        api.kwargs = [KeywordParameter.from_info(x) for x in
                      info.get("kwargs", {}).values()]

        return api
