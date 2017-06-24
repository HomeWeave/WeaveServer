from flask import Blueprint

root_handler = Blueprint('root_handler', __name__, static_folder='static', static_url_path="/static")

@root_handler.route('')
def root():
    with open("static/index.html") as f:
        return f.read()


