"""
Exposes ShellService which has a purpose similar to a shell.
"""

from app.views.simple_header_view import SimpleHeaderView
from .base import BaseService, BlockingServiceStart
#from app.applications import apps as applications


class ShellService(BaseService, BlockingServiceStart):
    """ A basic shell. """

    NAMESPACE = "/shell"

    def __init__(self, socketio):
        #self.apps = apps or applications
        view = SimpleHeaderView(self.NAMESPACE, socketio, "Hello!")
        super().__init__(view=view)

