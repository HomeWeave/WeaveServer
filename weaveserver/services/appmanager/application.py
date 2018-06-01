import os


class RPCInfo(object):
    def __init__(self, name, desc, apis, req_queue, res_queue, req_schema,
                 res_schema):
        self.name = name
        self.description = desc
        self.apis = apis
        self.request_queue = req_queue
        self.response_queue = res_queue
        self.request_schema = req_schema
        self.response_schema = res_schema

    def to_json(self):
        return {
            "name": self.name,
            "description": self.description,
            "apis": self.apis,
            "request_queue": self.request_queue,
            "response_queue": self.response_queue,
            "request_schema": self.request_schema,
            "response_schema": self.response_schema
        }


class AppResource(object):
    def __init__(self, app_resource_dir, path, mime):
        self.app_resource_dir = app_resource_dir
        self.path = path
        self.mime = mime

    def read(self):
        with open(os.path.join(self.app_resource_dir, self.path), 'rb') as inp:
            return inp.read()

    @staticmethod
    def create(app_resource_dir, path, mime, content):
        path = path.lstrip("/")
        full_path = os.path.join(app_resource_dir, path)
        try:
            os.makedirs(os.path.dirname(full_path))
        except:
            pass
        with open(full_path, "wb") as out:
            out.write(content)

        return AppResource(app_resource_dir, path, mime)


class Application(object):
    def __init__(self):
        self.rpcs = {}
        self.resources = {}
        self.package_name = None
        self.status_card = None
        self.system_app = False

    def register_rpc(self, rpc_info):
        self.rpcs[rpc_info.name] = rpc_info

    def register_app_resource(self, resource):
        self.resources[resource.path] = resource

    def register_status_card(self, resource):
        self.status_card = resource
