def chain_event(chain, obj):
    if "success" in chain:
        if chain["success"]["type"] == "$render":
            chain["success"] = obj
            obj["success"] = {"type": "$render"}
            obj["error"] = {
                "type": "$util.banner",
                "options": {
                    "title": "Error",
                    "description": "Uh oh, something went wrong."
                }
            }
        else:
            chain_event(chain["success"], obj)
    else:
        chain.update(obj)
        chain["success"] = {"type": "$render"}
        chain["error"] = {
            "type": "$util.banner",
            "options": {
                "title": "Error",
                "description": "Uh oh, something went wrong."
            }
        }

class ModuleProcessor(object):
    def __init__(self, modules):
        self.modules = modules

    def process(self, template, params):
        module_id = params["module_id"]
        if module_id in self.modules:
            self.insert_module_data(template, module_id)
            self.insert_module_ui(template, module_id)

    def insert_module_data(self, template, module_id):
        res = sorted(self.modules.values(), key=lambda x: x["name"])
        for mod in res:
            mod["active"] = mod["id"] == module_id
        template["$jason"]["head"]["data"]["posts"] = res

    def insert_module_ui(self, template, module_id):
        sections = template["$jason"]["head"]["templates"]["body"]["sections"]
        sections.append(self.modules[module_id]["ui"])
