from .base import BaseView


class SimpleBackgroundView(BaseView):
    def __init__(self, msg):
        self.msg = msg

    def html(self):
        return render_template('simple.html', title=self.msg)

