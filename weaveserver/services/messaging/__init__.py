from .server import MessageService


__meta__ = {
    "name": "Messaging Server",
    "class": MessageService,
    "deps": [],
    "config": [
        {
            "name": "redis_config",
            "loaders": [
                {"type": "env"},
                {"type": "sysvarfile"}
            ]
        }
    ]
}
