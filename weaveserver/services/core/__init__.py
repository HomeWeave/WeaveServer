from .service import CoreService


__meta__ = {
    "name": "HomeWeave Core",
    "class": CoreService,
    "deps": [],
    "config": [
        {
            "name": "core_config",
            "loaders": [
                {"type": "env"},
                {"type": "sysvarfile"}
            ]
        }
    ]
}
