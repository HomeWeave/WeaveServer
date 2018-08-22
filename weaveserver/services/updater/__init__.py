from .service import UpdaterService

__meta__ = {
    "name": "Software Updater",
    "class": UpdaterService,
    "deps": ["http"],
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
