import json
import logging
import os

from bottle import Bottle, static_file, request, response
from weavelib.exceptions import ObjectNotFound
from weavelib.rpc import RPCClient


logger = logging.getLogger(__name__)


def return_response(code, obj):
    response.status = code
    response.content_type = 'application/json'
    return json.dumps(obj)


class RPCHandler(object):
    def __init__(self, service):
        self.rpc_info_cache = {}
        self.appmgr_client = service.rpc_client
        self.service_token = service.token

    def handle(self, package_name, rpc_name, api_name, args, kwargs):
        rpc_info = self.appmgr_client["rpc_info"](package_name, rpc_name,
                                                  _block=True)

        rpc_client = RPCClient(rpc_info, self.service_token)
        rpc_client.start()
        res = rpc_client[api_name](*args, _block=True, **kwargs)
        rpc_client.stop()

        return res


class HTTPServer(Bottle):
    def __init__(self, service, plugin_path):
        super().__init__()
        self.service = service

        self.static_path = os.path.join(os.path.dirname(__file__), "static")
        self.plugin_path = plugin_path
        self.rpc_handler = RPCHandler(service)

        self.route("/")(self.handle_root)
        self.route("/apps/<path:path>")(self.handle_apps)
        self.route("/api/rpc", method="POST")(self.handle_rpc)

        logger.info("Temp Dir for HTTP: %s", plugin_path)

    def handle_root(self):
        return self.handle_static("/index.html")

    def handle_apps(self, path):
        return static_file(path, root=os.path.join(self.plugin_path))

    def handle_rpc(self):
        body = json.load(request.body)
        # TODO: Should be able to deduce package_name.
        package_name = body.get("package_name")
        rpc_name = body.get("rpc_name")
        api_name = body.get("api_name")
        args = body.get("args")
        kwargs = body.get("kwargs")

        try:
            res = self.rpc_handler.handle(package_name, rpc_name, api_name,
                                          args, kwargs)
            return return_response(200, res)
        except ObjectNotFound:
            return return_response(404, {"error": "RPC not found."})
        except (TypeError, KeyError):
            return return_response(400, {"error": "Bad request for API."})
        except:
            return return_response(500, {"error": "Internal Server Error."})
