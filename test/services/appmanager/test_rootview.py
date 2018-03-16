from copy import deepcopy

from weaveserver.services.appmanager.rootview import ModuleProcessor, RootView
from weaveserver.services.appmanager.rootview import chain_event


class TestChainEvent(object):
    def test_chain_in_empty_object(self):
        obj = {}
        new_event = {"type": "type1"}

        chain_event(obj, new_event)

        assert obj == {
            "type": "type1",
            "success": {"type": "$render"},
            "error": {
                "type": "$util.banner",
                "options": {
                    "title": "Error",
                    "description": "Uh oh, something went wrong."
                }
            }
        }

    def test_chain_first_level(self):
        obj = {
            "type": "type1",
            "success": {"type": "$render"},
            "error": {
                "type": "$util.banner",
                "options": {
                    "title": "Error",
                    "description": "Uh oh, something went wrong."
                }
            }
        }
        new_event = {"type": "type2"}

        chain_event(obj, new_event)

        assert obj == {
            "type": "type1",
            "success": {
                "type": "type2",
                "success": {"type": "$render"},
                "error": {
                    "type": "$util.banner",
                    "options": {
                        "title": "Error",
                        "description": "Uh oh, something went wrong."
                    }
                }
            },
            "error": {
                "type": "$util.banner",
                "options": {
                    "title": "Error",
                    "description": "Uh oh, something went wrong."
                }
            }
        }

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
                "view": {"test": "blah"}
            },
            "_dashboard": {
                "id": "_dashboard",
                "name": "Dashboard",
                "view": {"hello": "world"}
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
                                "view": {"hello": "world"},
                                "active": False
                            },
                            {
                                "name": "Settings",
                                "id": "_settings",
                                "view": {"test": "blah"},
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
