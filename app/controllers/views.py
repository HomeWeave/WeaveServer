import json

from flask import Blueprint
from flask import jsonify
from flask.views import MethodView


from app.views import view_manager


view_handler = Blueprint('view_handler', __name__)

class ViewController(MethodView):
    def get(self):
        return view_manager.view.html()


view_handler.add_url_rule('/', view_func=ViewController.as_view('views'))

