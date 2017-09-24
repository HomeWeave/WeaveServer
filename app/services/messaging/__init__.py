from .server import MessageService


__meta__ = {
    "name": "Messaging Server",
    "class": MessageService,
    "deps": ["logging"],
    "config": [
        {
            "name": "queues",
            "loaders": [
                {"path": "messaging_queues.json", "type": "json"},
            ]
        },
        {
            "name": "redis_config",
            "loaders": [
                {"type": "env"},
                {"type": "sysvarfile"}
            ]
        }
    ]
}
