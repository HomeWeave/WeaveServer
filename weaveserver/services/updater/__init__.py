from .service import UpdaterService

__meta__ = {
    "name": "Software Updater",
    "class": UpdaterService,
    "deps": ["messaging", "http"],
    "config": []
}
