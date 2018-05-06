from weavelib.services import BaseService

from weaveserver.core.services import ServiceManager
from weaveserver.services.simpledb import SimpleDatabaseService


AUTH = {
    "auth1": {
        "type": "SYSTEM",
        "appid": "appmgr"
    },
    "auth2": {
        "appid": "appid2"
    }
}


class DummyService(BaseService):
    def __init__(self, token):
        super(DummyService, self).__init__(token)

    def api1(self):
        return "OK"

    def on_service_start(self):
        self.rpc_server.start()
        self.relative_url = self.http.register_folder("test_dir")

    def on_service_stop(self):
        self.rpc_server.stop()


class TestSimpleDBService(object):
    def setup_class(cls):
        cls.service_manager = ServiceManager()
        cls.service_manager.apps = AUTH
        cls.service_manager.start_services(["messaging"])
        cls.db = SimpleDatabaseService("auth1", None)
        cls.db.on_service_start()

    def teardown_class(cls):
        cls.service_manager.stop()
        cls.db.service_stop()
