import os

class BaseConfig(object):
    PORT = 5000
    SECRET_KEY = '\xd1\xc2#|e\xf4\x15\x9e\xcbk\x96l\xcdw\x87\xc9W\xa5\x82Y\xb0y\x99\x98'

class LocalConfig(BaseConfig):
    DEBUG = True


class PiConfig(BaseConfig):
    DEBUG = False


if "alarm" in os.uname().nodename:
    config = PiConfig()
else:
    config = LocalConfig()


for key in dir(config):
    globals()[key] = getattr(config, key)

