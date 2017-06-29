"""
A dummy controller to handle static content.
"""
from flask import Blueprint

handler = Blueprint('root_handler', __name__, static_folder='static',
                    static_url_path="/static")

@handler.route('')
def root():
    with open("static/index.html") as inp:
        return inp.read()


