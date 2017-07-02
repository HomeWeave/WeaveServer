"""
Subclass BaseApplication for all the apps.
"""

class BaseApplication(object):
    """
    Represents the basic properties/functionalities of an app.
    """

    ICON = "fa-pencil-square-o"
    NAME = ""
    DESCRIPTION = ""

    def __init__(self):
        pass

    def name(self):
        return self.NAME or self.__class__.__name__

    def icon(self):
        return self.ICON

    def description(self):
        return self.DESCRIPTION or ""
