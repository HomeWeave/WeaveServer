import eventlet
eventlet.monkey_patch()

import sys


if __name__ == '__main__':
    if sys.argv[1] == 'server':
        from app.main import create_app
        flask_app, sock_app = create_app()
        port = flask_app.config["PORT"]
        sock_app.run(flask_app, host="0.0.0.0", debug=True, use_reloader=False)
    elif sys.argv[1] == 'messaging':
        from app.messaging_app import create_app
        app = create_app()
        app.run()

