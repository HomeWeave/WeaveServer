import time
from unittest.mock import Mock

from weavelib.messaging import Receiver
from weavelib.rpc import RPCClient
from weavelib.services import BackgroundThreadServiceStart

from weaveserver.services.core.service import CoreService
from weaveserver.services.http.service import HTTPService
from weaveserver.services.updater.service import UpdaterService, UpdateScanner


AUTH = {
    "auth1": {
        "type": "SYSTEM",
        "appid": "auth1",
        "package": "core",
    },
    "auth2": {
        "type": "SYSTEM",
        "appid": "auth2",
        "package": "updater",
    },
    "auth3": {
        "type": "SYSTEM",
        "appid": "auth3",
        "package": "http",
    }
}


class ThreadedUpdaterService(BackgroundThreadServiceStart, UpdaterService):
    pass


class ThreadedHTTPService(BackgroundThreadServiceStart, HTTPService):
    pass


class TestUpdateScanner(object):
    def setup_method(self):
        self.update_check_freq_backup = UpdateScanner.UPDATE_CHECK_FREQ
        UpdateScanner.UPDATE_CHECK_FREQ = 5

        self.core_service = CoreService("auth1",
                                        {"core_config": {}, "apps": AUTH})
        self.core_service.service_start()
        self.core_service.wait_for_start(30)

        self.core_service.message_server.register_application(AUTH["auth2"])
        self.core_service.message_server.register_application(AUTH["auth3"])

        # Wait till it starts.
        receiver = Receiver("/_system/root_rpc/request")
        while True:
            try:
                receiver.start()
                break
            except:
                time.sleep(1)

        self.http_service = ThreadedHTTPService("auth3", None)
        self.http_service.service_start()
        self.http_service.wait_for_start(30)

    def teardown_method(self):
        UpdateScanner.UPDATE_CHECK_FREQ = self.update_check_freq_backup

        self.http_service.service_stop()
        self.core_service.service_stop()

    def test_simple_update(self):
        mock_repo = Mock()
        mock_repo.needs_pull = Mock(return_value=False)
        UpdateScanner.list_repos = lambda x, y: ["dir"]
        UpdateScanner.get_repo = lambda x, y: mock_repo

        service = ThreadedUpdaterService("auth2",
                                         {"plugins": {"PLUGIN_DIR": ""}})
        service.service_start()
        assert service.wait_for_start(30)

        while service.get_status() != "No updates available.":
            time.sleep(1)

        mock_repo.asssert_called_with("dir")

        mock_repo.needs_pull = Mock(return_value=True)
        time.sleep(8)
        assert service.get_status() == "Updates available."

        service.service_stop()

    def test_trigger_update_when_no_update(self):
        UpdateScanner.UPDATE_CHECK_FREQ = 1000

        mock_repo = Mock()
        mock_repo.needs_pull = Mock(return_value=False)
        UpdateScanner.list_repos = lambda x, y: ["dir"]
        UpdateScanner.get_repo = lambda x, y: mock_repo

        service = ThreadedUpdaterService("auth2",
                                         {"plugins": {"PLUGIN_DIR": ""}})
        service.service_start()
        assert service.wait_for_start(30)

        service.update_status("dummy")

        rpc = RPCClient(service.rpc.info_message)
        rpc.start()

        rpc["perform_upgrade"](_block=True)

        assert service.get_status() == "No updates available."

        service.service_stop()
