from threading import RLock

from weavelib.exceptions import ObjectAlreadyExists, ObjectNotFound


class BaseApplication(object):
    def __init__(self, name, app_id):
        self.name = name
        self.app_id = app_id


class SystemApplication(BaseApplication):
    pass


class Plugin(BaseApplication):
    def __init__(self, name, app_id, url):
        super(Plugin, self).__init__(name, app_id)
        self.url = url


class ApplicationRegistry(object):
    def __init__(self, apps=None):
        self.apps = {x: SystemApplication(x, y) for x, y in (apps or [])}
        self.apps_lock = RLock()

    def register_plugin(self, name, app_id, url):
        with self.apps_lock:
            if app_id in self.apps:
                raise ObjectAlreadyExists(name)

            plugin = Plugin(name, app_id, url)
            self.apps[app_id] = plugin

    def unregister_plugin(self, app_id):
        with self.apps_lock:
            try:
                self.apps.pop(app_id)
            except KeyError:
                raise ObjectNotFound(app_id)

    def get_app_info(self, app_id):
        with self.apps_lock:
            try:
                app = self.apps[app_id]
            except KeyError:
                raise ObjectNotFound(app_id)

        return {
            "app_name": app.name,
            "app_type": "plugin" if isinstance(app, Plugin) else "system",
            "app_id": app_id,
            "app_url": app.url if isinstance(app, Plugin) else None
        }
