"""
Contains a base class for all services. All services must inherit
BlockingServiceStart if they wish to start in the service_manager thread
and display a UI, or BackgroundServiceStart if they wish to start is a new
thread without a UI.
"""

import threading
import logging


logger = logging.getLogger(__name__)

class BaseService(object):
    """ Base class for all services """
    def __init__(self, **kwargs):
        self.name = kwargs.pop("name", self.__class__.__name__)
        self._view = kwargs.pop("view", None)
        super().__init__(**kwargs)

    def view(self):
        """ Returns an instance of SimpleBackgroundView()  for view_manager
        to display. The instance returns is also set to self.view. The function
        should typically be overriden"""
        return self._view

    def get_sockets(self):
        return self._view.get_sockets()

    def service_stop(self):
        pass

class BlockingServiceStart(object):
    """ Starts the service in the current thread. """
    def __init__(self, **kwargs):
        self.target = kwargs.pop("target", self.on_service_start)
        self.target_args = kwargs.pop("target_args", ())
        self.target_kwargs = kwargs.pop("target_kwargs", {})
        super().__init__(**kwargs)

    def service_start(self):
        try:
            return self.target(*self.target_args, **self.target_kwargs)
        except:
            logger.exception("Failed to start service.")

    def on_service_start(self, *args, **kwargs):
        pass

class BackgroundServiceStart(object):
    """ Starts the service in the background thread. """
    def __init__(self, **kwargs):
        self.target = kwargs.get("target") or self.on_service_start
        self.target_args = kwargs.get("target_args") or ()
        self.target_kwargs = kwargs.get("target_kwargs") or {}
        super().__init__(**kwargs)

    def service_start(self):
        thread = threading.Thread(target=self.service_start_target)
        thread.start()

    def service_start_target(self):
        try:
            self.target(*self.target_args, **self.target_kwargs)
        except:
            logger.exception("Failed to start service.")

    def on_service_start(self, *args, **kwargs):
        pass

