import threading
import traceback
import logging

from app.views import SimpleBackgroundView

logger = logging.getLogger(__name__)

class BaseService(object):
    def __init__(self, **kwargs):
        self.name =  kwargs.pop("name", self.__class__.__name__)
        self.observer = kwargs.pop("observer", None)
        super().__init__(**kwargs)

    def view(self):
        return SimpleBackgroundView()

    def service_stop(self):
        pass

class BlockingServiceStart(object):
    def __init__(self, **kwargs):
        self.target = kwargs.pop("target", self.on_service_start)
        self.target_args = kwargs.pop("target_args",  ())
        self.target_kwargs = kwargs.pop("target_kwargs", {})
        super().__init__(**kwargs)

    def service_start(self):
        try:
            return self.target(*self.target_args, **self.target_kwargs)
        except Exception as e:
            print("Failed to start..")
            logger.exception("Failed to start service.")

class BackgroundServiceStart(object):
    def __init__(self, **kwargs):
        self.target = kwargs.get("target") or self.on_service_start
        self.target_args = kwargs.get("target_args") or ()
        self.target_kwargs = kwargs.get("target_kwargs") or {}
        super().__init__(**kwargs)

    def service_start(self):
        t = threading.Thread(target=self.service_start_target)
        t.start()

    def service_start_target(self):
        try:
            self.target(*self.target_args, **self.target_kwargs)
        except Exception as e:
            logger.exception("Failed to start service.")


