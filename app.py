from flask import Flask

from app.main import create_app


if __name__ == '__main__':
    app = create_app()

    port = app.config["PORT"]

    server = Flask(__name__)
    server.wsgi_app = app
    server.run(host="", port=port, threaded=True, debug=True)

