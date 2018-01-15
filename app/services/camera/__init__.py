from .service import CameraService

__meta__ = {
    "name": "Camera",
    "class": CameraService,
    "deps": ["messaging"],
    "config": [
        {
            "name": "dahua",
            "loaders": [
                {"type": "env"},
                {"type": "sysvarfile"},
            ]
        }
    ]
}
