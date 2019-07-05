from threading import RLock
from uuid import uuid4

from weavelib.exceptions import ObjectNotFound


class BaseApplication(object):
    def __init__(self, name, url, app_token):
        self.name = name
        self.url = url
        self.app_token = app_token


class SystemApplication(BaseApplication):
    pass


class Plugin(BaseApplication):
    pass


class ApplicationRegistry(object):
    def __init__(self, apps=None):
        self.apps_by_token = {}
        self.apps_lock = RLock()

        for name, url, token in (apps or []):
            self.apps_by_token[token] = SystemApplication(name, url, token)

    def register_plugin(self, name, url):
        with self.apps_lock:
            token = "app-token-" + str(uuid4())
            self.apps_by_token[token] = Plugin(name, url, token)
            return token

    def unregister_plugin(self, token):
        with self.apps_lock:
            try:
                self.apps_by_token.pop(token)
            except KeyError:
                raise ObjectNotFound(token)

    def get_app_info(self, app_token):
        with self.apps_lock:
            try:
                app = self.apps_by_token[app_token]
            except KeyError:
                raise ObjectNotFound(app_token)

        return {
            "app_name": app.name,
            "app_type": "plugin" if isinstance(app, Plugin) else "system",
            "app_url": app.url,
        }
