import os

import appdirs
import pytest

from weavelib.exceptions import ObjectNotFound
from weavelib.rpc import RPCClient

import weaveserver.services.simpledb.service as service
from weaveserver.services.simpledb import SimpleDatabaseService
from weaveserver.services.simpledb.service import SimpleDatabase


class TestSimpleDBService(object):
    @classmethod
    def setup_class(cls):
        cls.rpc_caller_backup = service.get_rpc_caller
        service.get_rpc_caller = lambda: {"package": "p"}

    @classmethod
    def teardown_class(cls):
        service.get_rpc_caller = cls.rpc_caller_backup

    def test_db_path(self):
        dbs = SimpleDatabaseService("token", {})
        expected_path = os.path.join(appdirs.user_data_dir("homeweave"), "db")
        assert dbs.db.path == expected_path

    def test_query_bad_key(self):
        db = SimpleDatabase(":memory:")
        db.start()
        with pytest.raises(ObjectNotFound):
            db.query("key")

    def test_insert_and_query(self):
        db = SimpleDatabase(":memory:")
        db.start()
        obj = {"value": [1, 2], "test": {}}
        db.insert("key", obj)

        assert db.query("key") == obj

        # Test replace
        db.insert("key", {})
        assert db.query("key") == {}
