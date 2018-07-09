from .service import PluginService

__meta__ = {
    "name": "Plugin Manager",
    "class": PluginService,
    "deps": ["messaging", "simpledb", "appmanager"],
    "config": [
        {
            "name": "plugins",
            "loaders": [
                {"type": "env"},
                {"type": "sysvarfile"}
            ]
        }
    ]
}
