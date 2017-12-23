"""
A dummy controller to handle static content.
"""
from flask import Blueprint
from flask import send_from_directory

handler = Blueprint('root_handler', __name__, static_url_path="/static")

@handler.route('')
def root():
    return send_from_directory('static', 'index.html')


