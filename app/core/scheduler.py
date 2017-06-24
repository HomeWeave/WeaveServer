
from apscheduler.schedulers.background import BackgroundScheduler

class Timer(object):
    def __init__(self):
        self.scheduler = BackgroundScheduler()

    def start(self):
        self.scheduler.start()

    def stop(self):
        self.scheduler.shutdown()

    def register(self, interval):
        def register_wrapper(fn):
            def function_wrapper():
                print("Timer invoke: " + repr(fn))
                fn()
            self.scheduler.add_job(function_wrapper, 'interval', seconds=interval,
                    max_instances=1)
            return fn
        return register_wrapper

timer = Timer()

