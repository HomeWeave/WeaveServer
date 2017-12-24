from .base import BaseComponent
from .dock_component import DockComponent


class ShellComponent(BaseComponent):
    def __init__(self, ws_manager):
        super(ShellComponent, self).__init__("/shell")
        self.ws_manager = ws_manager
        self.apps_stack = []
        self.dock_component = DockComponent(self)

    def activate(self):
        self.ws_manager.register(self.dock_component)
        self.dock_component.activate()

    def deactivate(self):
        self.dock_component.deactivate()
        self.ws_manager.unregister(self.dock_component)
