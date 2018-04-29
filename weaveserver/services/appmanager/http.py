import json
import logging
import os

from bottle import Bottle, static_file, request, response
from weavelib.rpc import RPCClient


logger = logging.getLogger(__name__)


def return_response(code, obj):
    response.status = code
    response.content_type = 'application/json'
    return json.dumps(obj)


class HTTPServer(Bottle):
    def __init__(self, service, plugin_path):
        super().__init__()
        self.service = service

        self.static_path = os.path.join(os.path.dirname(__file__), "static")
        self.plugin_path = plugin_path

        self.route("/static/<path:path>")(self.handle_static)
        self.route("/")(self.handle_root)
        self.route("/apps/<path:path>")(self.handle_apps)
        self.route("/rpc/<path:path>")(self.handle_rpc)
        self.route("/views/<path:path>")(self.handle_view)
        self.route("/api/status")(self.handle_status)

        logger.info("Temp Dir for HTTP: %s", plugin_path)

    def handle_static(self, path):
        logger.info("Static: %s (within %s)", path, self.static_path)
        return static_file(path, root=self.static_path)

    def handle_root(self):
        return self.handle_static("/index.html")

    def handle_apps(self, path):
        return static_file(path, root=os.path.join(self.plugin_path))

    def handle_rpc(self, path):
        body = json.load(request.body)
        api_name = body.get("api_name")
        args = body.get("args")
        kwargs = body.get("kwargs")
        rpc_info = self.service.all_rpcs.get(path)

        if not rpc_info or not api_name:
            return return_response(404, {"error": "No such API."})

        rpc_client = RPCClient(rpc_info)

        rpc_client.start()
        try:
            res = rpc_client[api_name](*args, _block=True, **kwargs)
        except (TypeError, KeyError):
            return return_response(400, {"error": "Bad request for API."})

        rpc_client.stop()

        return return_response(200, res)

    def handle_view(self, path):
        pass

    def handle_status(self):
        return {
            "plugins": len(self.service.plugins),
            "rules": 0,
            "version": self.service.version,
        }
