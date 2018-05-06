from .service import SimpleDatabaseService

__meta__ = {
    "name": "Simple Database",
    "class": SimpleDatabaseService,
    "deps": ["messaging", "appmanager"],
    "config": []
}
