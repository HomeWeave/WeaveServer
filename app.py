import socketio

from app.main import create_app


if __name__ == '__main__':
    flask_app, sock_app = create_app()

    port = flask_app.config["PORT"]

    #sock_app.run(host="", port=port, threaded=True, debug=True)
    sock_app.run(flask_app, debug=True, use_reloader=False)

