import pytest

from weavelib.exceptions import ObjectNotFound

from messaging.application_registry import ApplicationRegistry


class TestApplicationService(object):
    def test_initial_system_apps(self):
        app = ApplicationRegistry([("name", "url", "token")])
        expected = {
            "app_name": "name",
            "app_type": "system",
            "app_url": "url",
        }

        assert app.get_app_info("token") == expected

    def test_plugin_apps(self):
        app = ApplicationRegistry()
        token = app.register_plugin("name", "url")
        expected = {
            "app_name": "name",
            "app_type": "plugin",
            "app_url": "url",
        }

        assert app.get_app_info(token) == expected

        app.unregister_plugin("url")

        with pytest.raises(ObjectNotFound):
            app.get_app_info(token)

    def test_invalid_plugin_unregister(self):
        app = ApplicationRegistry()
        with pytest.raises(ObjectNotFound):
            app.unregister_plugin("invalid-token")
