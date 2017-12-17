

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


class KeywordParameter(Parameter):
    positional = False


class API(object):
    def __init__(self, unique_id, name, desc, params=None):
        self.id = unique_id
        self.name = name
        self.description = desc
        self.args = [x for x in (params or []) if x.positional]
        self.kwargs = [x for x in (params or []) if not x.positional]

    @property
    def schema(self):
        obj = {
            "type": "object",
            "properties": {
                "command": {"enum": [self.id]},
            },
            "additionalProperties": False,
            "required": ["command"],
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
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "args": [x.info for x in self.args],
            "kwargs": {x.name: x.info for x in self.kwargs}
        }

    def __call__(self, func, params):
        return func(*params["args"], **params["kwargs"])
