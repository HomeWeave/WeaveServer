import eventlet
eventlet.monkey_patch()  # NOLINT


import importlib
import sys
from app.main import create_app
from app.core.logger import configure_logging


def handle_launch(name):
    import signal
    from app.core.config_loader import get_config
    module = importlib.import_module(name)
    meta = module.__meta__

    config = get_config(meta.get("config"))
    app = meta["class"](config)

    signal.signal(signal.SIGTERM, lambda x, y: app.on_service_stop())
    signal.signal(signal.SIGINT, lambda x, y: app.on_service_stop())
    print("gi")
    app.on_service_start()


if __name__ == '__main__':
    configure_logging()
    if sys.argv[1] == 'main':
        main_app = create_app()
        main_app.start()
    elif sys.argv[1] == 'launch-service':
        handle_launch(sys.argv[2])
    else:
        print("Invalid mode.")
