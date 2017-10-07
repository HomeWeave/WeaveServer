from .service import DiscoveryService

__meta__ = {
    "name": "Discovery server",
    "class": DiscoveryService,
    "deps": ["messaging"],
    "config": []
}
