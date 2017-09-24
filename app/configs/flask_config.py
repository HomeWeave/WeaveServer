"""
Project level cofiguration. All the values specifed in the classes will be
available as app.config[..]
"""
# pylint: disable=too-few-public-methods

import os
import sys


class BaseConfig(object):
    """ Configurations shared by all environments"""
    PORT = 5000
    SECRET_KEY = '\xd1\xc2#|e\xf4\x15\x9e\xcbk\x96l\xcdw\x87\xc9W\xa5\x82Y\xb0y\x99\x98'

class LocalConfig(BaseConfig):
    """ Configurations when running on dev machine """
    DEBUG = True


class PiConfig(BaseConfig):
    """ Configurations when running on RPI """
    DEBUG = False


def export_config():
    """
    Selects one of the above envs using `uname` and exports all the values
    to module level scope.
    """

    if "alarm" in os.uname().nodename:
        config = PiConfig()
    else:
        config = LocalConfig()

    for key in dir(config):
        globals()[key] = getattr(config, key)

export_config()
