from .base import BaseService


def configure_flask_logging(app):
    for handler in logging.getLogger().handlers:
        app.logger.addHandler(handler)


class FlaskServer(BaseService):
    def __init__(self):
        params = {
            "template_folder": "../templates",
            "static_folder": "../static"
        }
        self.flask_app = Flask(__name__, **params)
        for prefix, controller in scan_blueprint():
            self.flask_app.register_blueprint(controller, url_prefix=prefix)
        configure_flask_logging(self.flask_app)

    def service_start(self, *args, **kwargs):
        from app.main import create_app
        flask_app, sock_app = create_app()
        port = flask_app.config["PORT"]
        sock_app.run(flask_app, host="0.0.0.0", debug=True, use_reloader=False)

    def service_stop(self):
        pass
