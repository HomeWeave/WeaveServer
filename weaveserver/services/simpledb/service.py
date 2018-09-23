import errno
import json
import logging
import os
from threading import Event

import appdirs
from peewee import SqliteDatabase, Proxy, Model, CharField, TextField
from peewee import DoesNotExist

from weavelib.exceptions import ObjectNotFound
from weavelib.rpc import RPCServer, ServerAPI, ArgParameter, get_rpc_caller
from weavelib.services import BaseService, BackgroundProcessServiceStart


logger = logging.getLogger(__name__)
proxy = Proxy()


def get_db_path():
    weave_base = appdirs.user_data_dir("homeweave")
    try:
        os.makedirs(weave_base)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise
    return os.path.join(weave_base, "db")


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
        database = proxy


class AppData(BaseModel):
    app_id = CharField(unique=True)
    app_key = CharField()
    app_value = JSONField()


class SimpleDatabase(object):
    def __init__(self, path):
        self.path = path

    def start(self):
        self.conn = SqliteDatabase(self.path)
        proxy.initialize(self.conn)
        self.conn.create_tables([AppData])

    def query(self, key):
        try:
            return AppData.get(AppData.app_id == get_rpc_caller_package(),
                               AppData.app_key == key).app_value
        except DoesNotExist:
            raise ObjectNotFound(key)

    def insert(self, key, value):
        query = AppData.insert(app_id=get_rpc_caller_package(), app_key=key,
                               app_value=value)
        query.on_conflict_replace().execute()


class SimpleDatabaseService(BackgroundProcessServiceStart, BaseService):
    def __init__(self, token, config):
        super().__init__(token)
        path = config["core"].get("DB_PATH") or get_db_path()
        self.db = SimpleDatabase(path)
        self.rpc = RPCServer("object_store", "Object Store for all plugins.", [
            ServerAPI("query", "Query for key", [
                ArgParameter("key", "Name of the key.", str),
            ], self.db.query),
            ServerAPI("insert", "Insert key-value pair", [
                ArgParameter("key", "Name of the key.", str),
                ArgParameter("value", "JSON Object", {}),
            ], self.db.insert)
        ], self, self.conn)
        self.shutdown = Event()

    def on_service_start(self, *args, **kwargs):
        super(SimpleDatabaseService, self).on_service_start(*args, **kwargs)
        self.rpc.start()
        self.db.start()
        self.notify_start()
        self.shutdown.wait()

    def on_service_stop(self):
        self.shutdown.set()
