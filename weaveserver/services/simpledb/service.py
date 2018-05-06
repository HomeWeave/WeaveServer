import json
import logging
import os
import sqlite3
from threading import Event

import appdirs
from peewee import Proxy, Model, CharField, TextField

from weavelib.services import BaseService, BackgroundThreadServiceStart
from weavelib.rpc import RPCServer, ServerAPI, get_rpc_caller


logger = logging.getLogger(__name__)
proxy = Proxy()


def get_rpc_caller_package():
    caller_app = get_rpc_caller()
    return caller_app["package"]


class JSONField(TextField):
    def db_value(self, value):
        return json.dumps(value)

    def python_value(self, value):
        if value is not None:
            return json.loads(value)


class BaseModel(Model):
    class Meta(object):
        db = proxy


class AppData(BaseModel):
    app_id = CharField(unique=True)
    app_key = CharField()
    app_value = JSONField()


class SimpleDatabase(object):
    def __init__(self, path):
        self.path = path

    def start(self):
        self.conn = sqlite3.connect(self.path)

    def query(self, key):
        try:
            return AppData.get(AppData.app_id == get_rpc_caller_package(),
                               AppData.app_key == key).app_value
        finally:
            pass


class SimpleDatabaseService(BackgroundThreadServiceStart, BaseService):
    def __init__(self, token, config):
        super().__init__(token)
        weave_base = appdirs.user_data_dir("homeweave")
        self.db = SimpleDatabase(os.path.join(weave_base, "db"))
        self.rpc = RPCServer("object_store", "Object Store for all plugins.", [
            ServerAPI("query", "Query for key", [str], self.db.query),
        ], self)
        self.shutdown = Event()

    def on_service_start(self, *args, **kwargs):
        self.db.start()
        self.notify_start()
        self.shutdown.wait()

    def on_service_stop(self):
        self.shutdown.set()
