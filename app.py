import eventlet
eventlet.monkey_patch()  # NOLINT


import importlib
import os
import sys
from weaveserver.main import create_app
from weaveserver.core.logger import configure_logging


def handle_launch():
    import signal
    from weaveserver.core.config_loader import get_config
    configure_logging()

    name = sys.argv[2]
    module = importlib.import_module(name)
    meta = module.__meta__

    config = get_config(meta.get("config"))
    app = meta["class"](config)

    signal.signal(signal.SIGTERM, lambda x, y: app.on_service_stop())
    signal.signal(signal.SIGINT, lambda x, y: app.on_service_stop())
    app.on_service_start()


def handle_quit(app):
    import signal
    app.on_service_stop()
    os.kill(os.getpid(), signal.SIGKILL)


if __name__ == '__main__':
    configure_logging()
    if sys.argv[1] == 'main':
        main_app = create_app()
        main_app.start()
    elif sys.argv[1] == 'launch-service':
        handle_launch()
    else:
        print("Invalid mode.")
