import pytest

from weavelib.exceptions import ObjectNotFound

from messaging.application_registry import ApplicationRegistry


class TestApplicationService(object):
    def test_initial_system_apps(self):
        app = ApplicationRegistry([("name", "url", "app_id", "token")])
        expected = {
            "app_name": "name",
            "app_type": "system",
            "app_url": "WEAVE-ENV",
            "app_id": "app_id"
        }

        assert app.get_app_info("token") == expected

    def test_plugin_apps(self):
        app = ApplicationRegistry()
        token = app.register_plugin("app_id", "name", "url")
        expected = {
            "app_name": "name",
            "app_type": "plugin",
            "app_url": "url",
            "app_id": "app_id"
        }

        assert app.get_app_info(token) == expected

        app.unregister_plugin(token)

        with pytest.raises(ObjectNotFound):
            app.get_app_info(token)

    def test_invalid_plugin_unregister(self):
        app = ApplicationRegistry()
        with pytest.raises(ObjectNotFound):
            app.unregister_plugin("invalid-token")
