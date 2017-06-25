from flask import render_template

class BaseView(object):
    def __init__(self):
        pass

    def html(self):
        return render_template('simple.html', title="Hello!")

