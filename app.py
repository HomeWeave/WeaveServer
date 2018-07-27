import eventlet
eventlet.monkey_patch()  # NOLINT


import importlib
import os
import sys
from weaveserver.main import create_app
from weaveserver.core.logger import configure_logging
from weaveserver.core.plugins import VirtualEnvManager, load_plugin_from_path


def handle_launch():
    import signal
    from weaveserver.core.config_loader import get_config
    configure_logging()

    token = sys.stdin.readline().strip()

    if len(sys.argv) > 2:
        # This is mostly for plugins. Need to change dir so that plugins see
        # their own directory as current directory.
        plugin_dir = sys.argv[1]
        os.chdir(plugin_dir)
        sys.path.append(plugin_dir)

        venv_path = sys.argv[2]
        venv = VirtualEnvManager(venv_path)
        venv.activate()

        plugin_info = load_plugin_from_path(os.path.dirname(plugin_dir),
                                            os.path.basename(plugin_dir))
        app = plugin_info["cls"](token, plugin_info["config"], venv_path)
    else:
        # Core Services.
        name = sys.argv[1]
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
