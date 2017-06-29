"""
Exposes SimpleBackgroundView that is a simple HTML view with <h1> and <h3>
"""
from .base import BaseView


class SimpleBackgroundView(BaseView):
    """
    A simple HTML view with self.msg shown within <h1> and self.args["subtitle"]
    shown in <h3>
    """
    def __init__(self, msg):
        self.msg = msg
        self.args = {"subtitle": ""}
        super().__init__()

    def html(self):
        return self.render_template('simple.html', title=self.msg, **self.args)

