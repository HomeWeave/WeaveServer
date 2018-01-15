"""
Contains a base class for all services. All services must inherit
BaseService. If they wish to start in background, they should use the
BackgroundServiceStart mixin before BaseService while inheriting.
"""


import logging
import os
import subprocess
import sys
import threading
from contextlib import suppress

import psutil

from .application import Application


logger = logging.getLogger(__name__)


class BaseService(object):
    """ Starts the service in the current thread. """
    def __init__(self, target_args=None, target_kwargs=None):
        self.target_args = () if target_args is None else target_args
        self.target_kwargs = {} if target_kwargs is None else target_kwargs
        self.app = Application(self)

    def service_start(self):
        self.before_service_start(*self.target_args, **self.target_kwargs)
        with suppress(Exception):
            return self.on_service_start(*self.target_args,
                                         **self.target_kwargs)

    def service_stop(self, timeout=None):
        self.on_service_stop()

    def before_service_start(self):
        pass

    def on_service_start(self, *args, **kwargs):
        pass

    def on_service_stop(self):
        pass

    def wait_for_start(self, timeout):
        pass

    def notify_start(self):
        pass

    def get_component_name(self):
        raise NotImplementedError("Must override.")

    def get_service_queue_name(self, queue_name):
        # TODO: Here is not a good choice. Move elsewhere.
        service_name = self.get_component_name()
        return "/services/{}/{}".format(service_name, queue_name)


class BackgroundThreadServiceStart(object):
    """ Mixin with BaseServer to start in the background thread. """
    def service_start(self):
        def thread_target():
            with suppress(Exception):
                self.on_service_start(self, *self.args, **self.kwargs)

        self.before_service_start(self, *self.args, **self.kwargs)
        self.service_thread = threading.Thread(target=thread_target)
        self.service_thread.start()
        self.started_event = threading.Event()

    def service_stop(self, timeout=15):
        self.on_service_stop()

        # TODO: stop self.service_thread

    def wait_for_start(self, timeout):
        return self.started_event.wait(timeout)

    def notify_start(self):
        self.started_event.set()


class BackgroundProcessServiceStart(object):
    SERVICE_BASE_PKG = "app.services"

    def service_start(self):
        self.started_event = threading.Event()
        self.child_thread = threading.Thread(target=self.child_process)
        self.child_thread.start()

    def service_stop(self, timeout=15):
        name = self.get_component_name()
        logger.info("Stopping background process: %s", name)
        psutil.Process(self.service_pid).terminate()
        try:
            self.service_proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            psutil.Process(self.service_pid).kill()

    def child_process(self):
        comp_name = self.get_component_name()
        name = self.SERVICE_BASE_PKG + "." + comp_name
        command = [sys.executable, "app.py", "launch-service", name]
        self.service_proc = subprocess.Popen(command, env=os.environ.copy(),
                                             stdout=subprocess.PIPE,
                                             stderr=subprocess.STDOUT)
        self.service_pid = self.service_proc.pid
        for line in iter(self.service_proc.stdout.readline, b''):
            content = line.strip().decode()
            if "SERVICE-STARTED-" + comp_name in content:
                self.started_event.set()
            else:
                logger.info("[%s]: %s", name, content)

    def notify_start(self):
        logger.info("SERVICE-STARTED-" + self.get_component_name())

    def wait_for_start(self, timeout):
        return self.started_event.wait(timeout)
