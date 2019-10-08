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
        self.apps_by_url = {}
        self.apps_lock = RLock()

        for name, url, token in (apps or []):
            app = SystemApplication(name, url, token)
            self.apps_by_token[token] = app
            self.apps_by_url[url] = app

    def register_plugin(self, name, url):
        token = "app-token-" + str(uuid4())
        plugin = Plugin(name, url, token)
        with self.apps_lock:
            self.apps_by_token[token] = plugin
            self.apps_by_url[url] = plugin
        return token

    def unregister_plugin(self, url):
        with self.apps_lock:
            try:
                app = self.apps_by_url.pop(url)
                self.apps_by_token.pop(app.app_token)
            except KeyError:
                raise ObjectNotFound(url)

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

    def get_app_by_url(self, url):
        with self.apps_lock:
            try:
                return self.apps_by_url[url]
            except KeyError:
                raise ObjectNotFound(url)
