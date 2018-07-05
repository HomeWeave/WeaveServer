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

    token = sys.stdin.readline().strip()

    name = sys.argv[1]
    if len(sys.argv) > 2:
        # This is mostly for plugins. Need to change dir so imports can succeed.
        os.chdir(sys.argv[2])
        sys.path.append(sys.argv[2])

    module = importlib.import_module(name)
    meta = module.__meta__

    config = get_config(meta.get("config"))
    app = meta["class"](token, config)

    signal.signal(signal.SIGTERM, lambda x, y: app.on_service_stop())
    signal.signal(signal.SIGINT, lambda x, y: app.on_service_stop())

    app.before_service_start()
    app.on_service_start()


def handle_main():
    configure_logging()

    main_app = create_app()
    main_app.start()
