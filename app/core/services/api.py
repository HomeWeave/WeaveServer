

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


class API(object):
    def __init__(self, unique_id, name, desc, params=None):
        self.id = unique_id
        self.name = name
        self.description = desc
        self.parameters = params or []

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

        if self.parameters:
            params_schema = {
                "type": "object",
                "properties": {p.name: p.schema for p in self.parameters}
            }
            params_schema["required"] = list(params_schema["properties"].keys())
            obj["properties"]["args"] = params_schema
            obj["required"].append("args")

        return obj

    @property
    def info(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "parameters": {x.name: x.info for x in self.parameters}
        }
