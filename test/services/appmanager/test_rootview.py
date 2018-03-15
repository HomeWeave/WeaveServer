from copy import deepcopy

from weaveserver.services.appmanager.rootview import ModuleProcessor, RootView


class TestModuleProcessor(object):
    def test_bad_module_id(self):
        mod = ModuleProcessor({})

        template = {}
        mod.process(template, {"module_id": "mod"}) is None
        assert template == {}

    def test_valid_module_id(self):
        template = {
            "$jason": {
                "head": {
                    "data": {},
                    "templates": {
                        "body": {
                            "sections": [
                                {"first": "section"}
                            ]
                        }
                    }
                }
            }
        }

        mod = ModuleProcessor({
            "_settings": {
                "id": "_settings",
                "name": "Settings",
                "ui": {"test": "blah"}
            },
            "_dashboard": {
                "id": "_dashboard",
                "name": "Dashboard",
                "ui": {"hello": "world"}
            }
        })

        expected = {
            "$jason": {
                "head": {
                    "data": {
                        "posts": [
                            {
                                "name": "Dashboard",
                                "id": "_dashboard",
                                "ui": {"hello": "world"},
                                "active": False
                            },
                            {
                                "name": "Settings",
                                "id": "_settings",
                                "ui": {"test": "blah"},
                                "active": True
                            },
                        ]
                    },
                    "templates": {
                        "body": {
                            "sections": [
                                {"first": "section"},
                                {"test": "blah"}
                            ]
                        }
                    }
                }
            }
        }
        cur = deepcopy(template)
        mod.process(cur, {"module_id": "_settings"})

        assert cur == expected

        expected["$jason"]["head"]["data"]["posts"][0]["active"] = True
        expected["$jason"]["head"]["data"]["posts"][1]["active"] = False
        expected["$jason"]["head"]["templates"]["body"]["sections"][1] =\
            {"hello": "world"}

        cur = deepcopy(template)
        mod.process(cur, {"module_id": "_dashboard"})

        assert cur == expected
