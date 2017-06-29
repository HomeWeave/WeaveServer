"""
Contains ViewManager class that acts like a central entity for managing
what's displayed on the screen.
"""
from .base import BaseView


class ViewManager(object):
    """
    `app` owns a ViewManager instance that contains the latest view. It communicates
    with `nav_channel` to send HTML to the websocket client.
    """
    def __init__(self, nav_channel):
        """
        Args:
            nav_channel: SocketChannel instance that will be used to communicate
                         changes in the view.
        """
        self._view = BaseView()
        self.nav_channel = nav_channel

    def get_view(self):
        """ Returns the latest view. """
        return self._view

    def replace_view(self, new_view):
        """
        Replaces self._view with the `new_view` and updates via
        self.nav_channel
        """
        self._view = new_view
        self.refresh_view()

    def refresh_view(self):
        """
        Sends the HTML of the current view to nav_channel.
        """
        self.nav_channel.update_view(self._view.html())
