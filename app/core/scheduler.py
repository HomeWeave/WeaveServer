"""
Timer uses APScheduler to generate events every specific number of seconds.
"""
import logging

from apscheduler.schedulers.background import BackgroundScheduler


logger = logging.getLogger(__name__)

class Timer(object):
    """
    Use as:
        timer = Timer()

        @timer.register(1) # Call every 1 second.
        def timer_targer():
            print("tick")

    """
    def __init__(self):
        self.scheduler = BackgroundScheduler()

    def start(self):
        """ Start the scheduler. """
        self.scheduler.start()

    def stop(self):
        """ Stop the scheduler. """
        self.scheduler.shutdown()

    def register(self, interval):
        """ Decorator for use with target function.
        Args:
            interval: Interval in seconds.
        """
        def register_wrapper(func):
            self.scheduler.add_job(func, 'interval', seconds=interval, max_instances=1)
            return func
        return register_wrapper
