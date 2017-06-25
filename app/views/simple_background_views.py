from .base import BaseView


class SimpleBackgroundView(BaseView):
    def __init__(self, msg):
        self.msg = msg
        self.args = {"subtitle": ""}
        super().__init__()

    def html(self):
        return render_template('simple.html', title=self.msg, **self.args)

