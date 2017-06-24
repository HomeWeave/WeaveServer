import os

class BaseConfig(object):
    PORT = 5000

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

